#!/usr/bin/env python3
'''
	dss_browser: browse dss files in the web browser.

	    dss_browser [file.dss ...] [--port 8765] [--no-browser]

	A single file tool using the python built in http server. The page uses
	htmx for interaction and shadcn/ui styling (tailwind + shadcn theme
	tokens). More files can be opened from the page (open button or drag &
	drop), every open file gets a tab. Records are shown as a graph (svg
	charts, png images for grids) and as a table, every record can be
	downloaded as csv.

	The file reads top to bottom: page templates, html helpers, charts, the
	views of a file, the http server & the svg icons at the end.
'''

import argparse
import errno
import fnmatch
import html
import io
import math
import os
import shutil
import struct
import sys
import tempfile
import webbrowser
import zlib
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import parse_qs, quote, urlparse

import numpy as np
import pandas as pd

import pyheclib as phl
from pyheclib.dssfile import REGULAR_TS, IRREGULAR_TS, PAIRED, GRID


MAX_ROWS = 500          # catalog rows shown
MAX_TABLE_ROWS = 100    # data rows shown in the record view
MAX_CHART_POINTS = 2000
PORT_TRIES = 3          # next ports tried when the port is in use

RECORD_KINDS = {
	"regular": ("Regular TS", lambda code: code in REGULAR_TS),
	"irregular": ("Irregular TS", lambda code: code in IRREGULAR_TS),
	"paired": ("Paired", lambda code: code in PAIRED),
	"grid": ("Grid", lambda code: code in GRID),
}

# shadcn chart colors
COLORS = ["#e76e50", "#2a9d90", "#274754", "#e8c468", "#f4a462", "#8b5cf6"]

# viridis color stops for grid images
VIRIDIS = np.array([[68, 1, 84], [59, 82, 139], [33, 145, 140], [94, 201, 98], [253, 231, 37]], dtype=float)



''' ** page templates ** '''

# {name} fields are filled with str.format, the css & scripts are plain strings
# put in as values, so their braces stay single

PAGE = '''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>DSS BROWSER - {title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=IBM+Plex+Sans:wght@400;500;600&display=swap" rel="stylesheet">
<script src="https://unpkg.com/htmx.org@2.0.4"></script>
<script src="https://cdn.tailwindcss.com"></script>
<script>{head_script}</script>
<style>{style}</style>
</head>
<body data-file="{file_id}" class="flex h-screen flex-col overflow-hidden bg-background text-foreground antialiased">
<header class="shrink-0 border-b">
	<div class="flex h-14 items-center gap-3 px-6">
		<div class="flex shrink-0 items-center gap-2 font-semibold tracking-tight">{logo_icon}DSS BROWSER</div>
		<nav class="flex min-w-0 items-center gap-1 overflow-x-auto rounded-lg bg-muted p-1 text-muted-foreground">{file_tabs}
			<button type="button" onclick="picker.click()" title="open dss files, or drop them on the page"
				class="inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium hover:text-foreground">{open_icon}Open</button>
		</nav>
		<input id="picker" type="file" accept=".dss" multiple hidden onchange="openFiles(this.files)">
		<span class="ml-auto shrink-0 text-xs text-muted-foreground">pyheclib <span class="font-mono">{version}</span></span>
		<button type="button" onclick="toggleTheme()" title="toggle dark / light theme"
			class="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border text-muted-foreground shadow-sm hover:bg-accent hover:text-foreground">
			<span class="dark:hidden">{moon_icon}</span><span class="hidden dark:inline">{sun_icon}</span></button>
	</div>
</header>
{body}

<div id="drop" class="fixed inset-4 z-40 hidden items-center justify-center rounded-md border-2 border-dashed border-foreground/40 bg-background/70 backdrop-blur-sm">
	<div class="flex flex-col items-center gap-3">{upload_icon}
		<div id="drop-text" class="font-semibold tracking-tight">Drop dss files to open them</div></div>
</div>
<div id="offline" class="fixed inset-0 z-50 hidden items-center justify-center bg-background/40 backdrop-blur-sm">
	<div class="rounded-md border bg-card p-6 text-center shadow-lg">
		<div class="font-semibold tracking-tight">Server stopped</div>
		<p class="mt-1 text-sm text-muted-foreground">The dss browser is not running, the page reconnects when it is back.</p>
	</div>
</div>
<script>{script}</script>
</body>
</html>
'''

# catalog on the left, the open record on the right
FILE_BODY = '''<main style="--left: 40%" class="grid min-h-0 flex-1 overflow-auto lg:grid-cols-[minmax(0,var(--left))_5px_minmax(0,1fr)] lg:grid-rows-[minmax(0,1fr)] lg:overflow-hidden">
	<section class="flex h-[32rem] min-w-0 flex-col border-b lg:h-auto lg:min-h-0 lg:border-b-0">
		<form class="flex h-16 shrink-0 items-center gap-2 border-b px-4" hx-get="/catalog" hx-target="#catalog"
			hx-trigger="load, input changed delay:250ms, change" hx-indicator="#catalog-loading">
			<input type="hidden" name="file" value="{file_id}">
			<div class="relative min-w-0 flex-1">
				<input name="search" placeholder="Search /A/B/C/D/E/F/ or parts like B=GAGE C=FLOW*" autocomplete="off"
					title="text matches anywhere in the pathname, A= .. F= match one part (* ? wild characters), all words must match"
					class="h-9 w-full rounded-md border border-input bg-transparent pl-3 pr-16 text-sm shadow-sm placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring">
				<span id="catalog-loading" class="htmx-indicator pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-xs text-muted-foreground">loading...</span>
			</div>
			{kind_select}
		</form>
		<div id="catalog" class="min-h-0 flex-1 overflow-auto"></div>
	</section>
	<div id="splitter" title="drag to resize" class="group hidden cursor-col-resize justify-center lg:flex">
		<div class="w-px bg-border transition-all group-hover:w-[3px] group-hover:bg-ring/40"></div></div>
	<section id="detail" class="flex h-[32rem] min-h-0 flex-col lg:h-auto">{detail}</section>
</main>'''

NO_FILE_BODY = '''<main class="flex min-h-0 flex-1 items-center justify-center p-6">
	<div class="flex w-full max-w-lg flex-col items-center gap-3 rounded-md border-2 border-dashed p-12 text-center">
		<span class="text-muted-foreground">{upload_icon}</span>
		<div class="font-semibold tracking-tight">No file open</div>
		<p class="text-sm text-muted-foreground">Drop dss files here, or</p>
		<button type="button" onclick="picker.click()"
			class="inline-flex h-9 items-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow hover:bg-primary/90">{open_icon}Open file</button>
	</div>
</main>'''

STYLE = '''
:root {
	--background: 0 0% 100%; --foreground: 240 10% 3.9%; --card: 0 0% 100%; --card-foreground: 240 10% 3.9%;
	--primary: 240 5.9% 10%; --primary-foreground: 0 0% 98%; --secondary: 240 4.8% 95.9%;
	--secondary-foreground: 240 5.9% 10%; --muted: 240 4.8% 95.9%; --muted-foreground: 240 3.8% 46.1%;
	--accent: 240 4.8% 95.9%; --accent-foreground: 240 5.9% 10%; --border: 240 5.9% 90%;
	--input: 240 5.9% 90%; --ring: 240 5.9% 10%; --radius: 0.5rem;
	--selection: #0063e1;   /* macos selected row blue */
	color-scheme: light;
}
.dark {
	--background: 240 10% 3.9%; --foreground: 0 0% 98%; --card: 240 10% 3.9%; --card-foreground: 0 0% 98%;
	--primary: 0 0% 98%; --primary-foreground: 240 5.9% 10%; --secondary: 240 3.7% 15.9%;
	--secondary-foreground: 0 0% 98%; --muted: 240 3.7% 15.9%; --muted-foreground: 240 5% 64.9%;
	--accent: 240 3.7% 15.9%; --accent-foreground: 0 0% 98%; --border: 240 3.7% 15.9%;
	--input: 240 3.7% 15.9%; --ring: 240 4.9% 83.9%;
	--selection: #0058d0;
	color-scheme: dark;
}
body { font-family: "IBM Plex Sans", ui-sans-serif, system-ui, sans-serif; }
.htmx-indicator { opacity: 0; transition: opacity 200ms; }
.htmx-request .htmx-indicator, .htmx-request.htmx-indicator { opacity: 1; }
tr.selected, tr.selected:hover { background: var(--selection); color: #fff; }
tr.selected .badge { background: rgb(255 255 255 / 0.2); color: #fff; }
thead th { box-shadow: inset 0 -1px 0 hsl(var(--border)); }   /* collapsed borders do not move with sticky headers */
[role="option"][aria-checked="false"] .check { visibility: hidden; }
[aria-selected="true"] { background: hsl(var(--background)); color: hsl(var(--foreground)); box-shadow: 0 1px 2px rgb(0 0 0 / 0.08); }
'''

# runs before the first paint
HEAD_SCRIPT = '''
// theme: saved choice, else the system setting
if ((localStorage.getItem("dss-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")) === "dark")
	document.documentElement.classList.add("dark");

// shadcn colors from the theme tokens in the style
tailwind.config = { darkMode: "class", theme: { extend: { colors: {
	border: "hsl(var(--border))", input: "hsl(var(--input))", ring: "hsl(var(--ring))",
	background: "hsl(var(--background))", foreground: "hsl(var(--foreground))",
	primary: { DEFAULT: "hsl(var(--primary))", foreground: "hsl(var(--primary-foreground))" },
	secondary: { DEFAULT: "hsl(var(--secondary))", foreground: "hsl(var(--secondary-foreground))" },
	muted: { DEFAULT: "hsl(var(--muted))", foreground: "hsl(var(--muted-foreground))" },
	accent: { DEFAULT: "hsl(var(--accent))", foreground: "hsl(var(--accent-foreground))" },
	card: { DEFAULT: "hsl(var(--card))", foreground: "hsl(var(--card-foreground))" },
}, borderColor: { DEFAULT: "hsl(var(--border))" }, fontFamily: {
	sans: ['"IBM Plex Sans"', "ui-sans-serif", "system-ui", "sans-serif"],
	mono: ['"IBM Plex Mono"', "ui-monospace", "SFMono-Regular", "monospace"],
}, borderRadius: { lg: "var(--radius)", md: "calc(var(--radius) - 2px)", sm: "calc(var(--radius) - 4px)" } } } };
'''

SCRIPT = '''
const currentFile = document.body.dataset.file;

function toggleTheme() {
	const dark = document.documentElement.classList.toggle("dark");
	localStorage.setItem("dss-theme", dark ? "dark" : "light");
}

// drag the divider to size the catalog & record sides, kept as a percentage
const splitter = document.getElementById("splitter");
if (splitter) {
	const main = splitter.parentElement;
	const saved = localStorage.getItem("dss-left");
	if (saved) main.style.setProperty("--left", saved);
	splitter.addEventListener("pointerdown", event => {
		event.preventDefault();
		splitter.setPointerCapture(event.pointerId);
		document.body.classList.add("select-none", "cursor-col-resize");
		const move = e => {
			const box = main.getBoundingClientRect();
			const left = Math.min(Math.max(e.clientX - box.left, 120), box.width - 200);
			main.style.setProperty("--left", (left / box.width * 100).toFixed(2) + "%");
		};
		splitter.addEventListener("pointermove", move);
		splitter.addEventListener("pointerup", () => {
			splitter.removeEventListener("pointermove", move);
			document.body.classList.remove("select-none", "cursor-col-resize");
			localStorage.setItem("dss-left", main.style.getPropertyValue("--left"));
		}, { once: true });
	});
}

// selected catalog row, kept when the catalog is filtered again
let selectedPath = new URLSearchParams(location.search).get("path");
function selectRow(row) {
	selectedPath = row.dataset.path;
	markSelected();
}
function markSelected() {
	document.querySelectorAll("#catalog tr[data-path]").forEach(r => r.classList.toggle("selected", r.dataset.path === selectedPath));
}
document.addEventListener("htmx:afterSwap", event => { if (event.target.id === "catalog") markSelected(); });

// open files: upload them, the server opens a copy
const drop = document.getElementById("drop");
function showDrop(visible, text = "Drop dss files to open them") {
	document.getElementById("drop-text").textContent = text;
	drop.classList.toggle("hidden", !visible);
	drop.classList.toggle("flex", visible);
}
async function openFiles(files) {
	let opened = null;
	for (const file of files) {
		showDrop(true, `Opening ${file.name}...`);
		const response = await fetch("/open?name=" + encodeURIComponent(file.name), { method: "POST", body: file });
		const text = await response.text();
		if (response.ok) opened = text;
		else alert(`Unable to open ${file.name}\\n${text}`);
	}
	showDrop(false);
	if (opened !== null) location = "/?file=" + opened;
}
async function closeFile(id) {
	await fetch("/close?file=" + id, { method: "POST" });
	if (String(id) === currentFile) location = "/";
	else location.reload();
}

let dragDepth = 0;
document.addEventListener("dragenter", event => {
	if (event.dataTransfer.types.includes("Files") && ++dragDepth === 1) showDrop(true);
});
document.addEventListener("dragleave", () => {
	if (dragDepth > 0 && --dragDepth === 0) showDrop(false);
});
document.addEventListener("dragover", event => event.preventDefault());
document.addEventListener("drop", event => {
	event.preventDefault();
	dragDepth = 0;
	showDrop(false);
	if (event.dataTransfer.files.length) openFiles(event.dataTransfer.files);
});

// shadcn style selects: set the hidden input & let the form see a change
function toggleSelect(button) {
	const list = button.nextElementSibling;
	list.hidden = !list.hidden;
}
function pickOption(option) {
	const root = option.closest(".select");
	const input = root.querySelector("input");
	root.querySelectorAll("[role=option]").forEach(o => o.setAttribute("aria-checked", o === option));
	root.querySelector(".label").textContent = option.textContent.trim();
	root.querySelector("[role=listbox]").hidden = true;
	if (input.value !== option.dataset.value) {
		input.value = option.dataset.value;
		input.dispatchEvent(new Event("change", { bubbles: true }));
	}
}
function closeSelects(except) {
	document.querySelectorAll(".select").forEach(root => {
		if (root !== except) root.querySelector("[role=listbox]").hidden = true;
	});
}
document.addEventListener("click", event => closeSelects(event.target.closest(".select")));
document.addEventListener("keydown", event => { if (event.key === "Escape") closeSelects(null); });

// graph / table tabs of the record view, the chosen tab is kept between records
let activeTab = null;
function showTab(button) {
	activeTab = button.dataset.tab;
	applyTabs(button.closest(".tabs"));
}
function applyTabs(root) {
	const buttons = [...root.querySelectorAll("[data-tab]")];
	const label = buttons.some(b => b.dataset.tab === activeTab) ? activeTab : buttons[0].dataset.tab;
	buttons.forEach(b => b.setAttribute("aria-selected", b.dataset.tab === label));
	root.querySelectorAll("[data-panel]").forEach(panel => panel.hidden = panel.dataset.panel !== label);
}
document.addEventListener("htmx:afterSwap", () => document.querySelectorAll(".tabs").forEach(applyTabs));

// blur the page while the server can not be reached
const offline = document.getElementById("offline");
async function ping() {
	let up = false;
	try {
		up = (await fetch("/ping", { cache: "no-store", signal: AbortSignal.timeout(2000) })).ok;
	} catch (error) {}
	const wasDown = !offline.classList.contains("hidden");
	offline.classList.toggle("hidden", up);
	offline.classList.toggle("flex", !up);
	const form = document.querySelector("form");
	if (up && wasDown && form) htmx.trigger(form, "change");   // refresh the catalog
}
setInterval(ping, 2000);
'''



''' ** html helpers ** '''

def esc(value):
	return html.escape(str(value), quote=True)


def icon(name, size="h-4 w-4"):
	return f'<svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true" class="{size} shrink-0"><path d="{ICONS[name]}"/></svg>'


def badge(text, outline=False):
	style = "border text-foreground" if outline else "bg-secondary text-secondary-foreground"
	return f'<span class="badge inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium whitespace-nowrap {style}">{esc(text)}</span>'


def panel(title, body, extra=""):
	''' fills the detail side, the body scrolls under a header as high as the catalog search bar '''
	return f'''<div class="flex h-16 shrink-0 items-center gap-2 border-b px-5">
		<h3 class="min-w-0 truncate font-semibold tracking-tight">{title}</h3>{extra}</div>
	<div class="min-h-0 flex-1 overflow-auto"><div class="flex min-h-full flex-col p-5 pb-12">{body}</div></div>'''   # padding inside, sticky headers stick at the very top


EMPTY_DETAIL = panel('<span class="font-normal text-muted-foreground">No record selected</span>',
	'<div class="flex flex-1 items-center justify-center text-sm text-muted-foreground">Select a record to view it</div>')


def tabs(panels):
	''' panels: [(label, icon name, html)], the first one is shown, the page script switches them '''
	buttons = "".join(f'''<button type="button" data-tab="{esc(label)}" aria-selected="{str(i == 0).lower()}" onclick="showTab(this)"
		class="inline-flex items-center gap-1.5 rounded-md px-3 py-1 text-sm font-medium hover:text-foreground">{icon(name)}{esc(label)}</button>'''
		for i, (label, name, _) in enumerate(panels))
	bodies = "".join(f'<div data-panel="{esc(label)}" class="mt-4"{" hidden" if i else ""}>{body}</div>'
		for i, (label, _, body) in enumerate(panels))
	return f'''<div class="tabs mt-6"><div class="inline-flex rounded-lg bg-muted p-1 text-muted-foreground">{buttons}</div>
		{bodies}</div>'''


def select(name, options):
	''' shadcn style select, options: [(value, label)], the first is chosen, the hidden input holds the value '''
	items = "".join(f'''<div role="option" data-value="{esc(value)}" aria-checked="{str(i == 0).lower()}" onclick="pickOption(this)"
		class="relative flex cursor-default select-none items-center whitespace-nowrap rounded-sm py-1.5 pl-2 pr-8 text-sm hover:bg-accent hover:text-accent-foreground">
		{esc(label)}<span class="check absolute right-2">{icon("check")}</span></div>''' for i, (value, label) in enumerate(options))
	return f'''<div class="select relative w-36 min-w-[4.5rem]">
		<input type="hidden" name="{esc(name)}" value="{esc(options[0][0])}">
		<button type="button" onclick="toggleSelect(this)"
			class="flex h-9 w-full items-center justify-between gap-2 whitespace-nowrap rounded-md border border-input bg-transparent px-3 text-sm shadow-sm focus:outline-none focus:ring-1 focus:ring-ring">
			<span class="label truncate">{esc(options[0][1])}</span><span class="opacity-50">{icon("arrow-down")}</span></button>
		<div role="listbox" hidden class="absolute right-0 z-50 mt-1 w-full rounded-md border bg-card p-1 text-card-foreground shadow-md">{items}</div></div>'''


def file_tab(browser, active):
	style = 'aria-selected="true"' if active else ""
	return f'''<span class="inline-flex items-center rounded-md text-sm font-medium" {style}>
		<a href="/?file={browser.id}" title="{esc(browser.filename)}" class="whitespace-nowrap py-1 pl-3 pr-1 hover:text-foreground">{esc(browser.name)}</a>
		<button type="button" onclick="closeFile({browser.id})" title="close" class="px-1.5 py-1 hover:text-foreground">{icon("close", "h-3.5 w-3.5")}</button></span>'''


def info_grid(items):
	cells = "".join(f'''<div><div class="text-xs text-muted-foreground">{esc(k)}</div>
		<div class="font-mono text-sm font-medium break-all">{esc(v)}</div></div>''' for k, v in items)
	return f'<div class="grid grid-cols-2 gap-4 sm:grid-cols-4">{cells}</div>'


def data_table(df, total=None):
	# separate borders belong to the cells, so they move with the sticky header
	head = "".join(f'<th class="h-9 border-r px-3 text-left font-medium text-muted-foreground last:border-r-0">{esc(c)}</th>'
		for c in [df.index.name or ""] + list(df.columns))
	cell = 'class="border-b border-r px-3 py-1.5 font-mono text-xs last:border-r-0"'
	rows = "".join(
		f"<tr><td {cell}>{esc(idx)}</td>" + "".join(f"<td {cell}>{esc(fmt(v))}</td>" for v in row) + "</tr>"
		for idx, row in zip(df.index, df.values))
	note = ""
	if total is not None and total > len(df):
		note = (f'<p class="px-3 py-2 text-xs text-muted-foreground">showing <span class="font-mono">{len(df)}</span> of '
			f'<span class="font-mono">{total}</span> rows, download csv for all</p>')
	# no scroll box of its own, the detail panel scrolls (keeps the header sticky)
	return f'''<div class="rounded-md border"><table class="w-full border-separate border-spacing-0 text-sm [&_tr:last-child_td]:border-b-0">
		<thead class="sticky top-0 bg-muted"><tr>{head}</tr></thead><tbody>{rows}</tbody></table></div>{note}'''


def fmt(value):
	if isinstance(value, (float, np.floating)):
		return "NaN" if np.isnan(value) else f"{value:.6g}"
	return value


def stats(values):
	values = np.asarray(values, dtype=float)
	valid = values[~np.isnan(values)]
	if not valid.size:
		return [("Min", "-"), ("Max", "-"), ("Mean", "-"), ("Missing", values.size)]
	return [("Min", f"{valid.min():.6g}"), ("Max", f"{valid.max():.6g}"),
			("Mean", f"{valid.mean():.6g}"), ("Missing", values.size - valid.size)]



''' ** charts ** '''

def nice_ticks(lo, hi, n=5):
	''' about n round tick values between lo & hi '''
	if not np.isfinite(lo) or not np.isfinite(hi):
		return []
	if hi == lo:
		hi, lo = hi + 1, lo - 1
	raw = (hi - lo) / n
	magnitude = 10 ** math.floor(math.log10(raw))
	step = min((s * magnitude for s in (1, 2, 2.5, 5, 10) if s * magnitude >= raw), default=raw)
	return list(np.arange(math.ceil(lo / step) * step, hi + step / 2, step))


def time_ticks(t0, t1):
	''' 6 (epoch seconds, label) ticks between t0 & t1, dates for long spans, else hours '''
	times = pd.date_range(pd.Timestamp(t0, unit="s"), pd.Timestamp(t1, unit="s"), periods=6)
	label_format = "%d %b %Y" if times[-1] - times[0] > pd.Timedelta(days=3) else "%d %b %H:%M"
	return [(t.value / 1e9, t.strftime(label_format)) for t in times]


def decimate(x, y, max_points=MAX_CHART_POINTS):
	''' keep min & max of buckets so peaks stay visible '''
	if x.size <= max_points:
		return x, y
	size = math.ceil(x.size / (max_points // 2))
	keep = []
	for start in range(0, x.size, size):
		bucket = y[start:start + size]
		if np.isnan(bucket).all():
			keep.append(start)
			continue
		keep.extend(sorted({start + int(np.nanargmin(bucket)), start + int(np.nanargmax(bucket))}))
	keep = np.array(keep)
	return x[keep], y[keep]


def segments(points):
	''' split (x, y) points into runs without missing values, a line breaks at every gap '''
	run = []
	for x, y in points:
		if np.isnan(y):
			if len(run) > 1:
				yield run
			run = []
		else:
			run.append((x, y))
	if len(run) > 1:
		yield run


def line_chart(lines, x_label="", y_label="", time_axis=False, markers=False):
	''' lines: [(label, x float array, y array)], x as epoch seconds for time axes '''
	width, height = 760, 300
	left, right, top, bottom = 64, 16, 16, 44

	xs = np.concatenate([x for _, x, _ in lines])
	ys = np.concatenate([y for _, _, y in lines])
	ys = ys[~np.isnan(ys)]
	if not xs.size or not ys.size:
		return '<p class="text-sm text-muted-foreground">no values to plot</p>'

	# data ranges, a little room above & below the lines
	x0, x1 = float(xs.min()), float(xs.max())
	y0, y1 = float(ys.min()), float(ys.max())
	if x1 == x0:
		x0, x1 = x0 - 1, x1 + 1
	pad = (y1 - y0) * 0.05 or 1.0
	y0, y1 = y0 - pad, y1 + pad

	# data -> svg coordinates
	sx = lambda v: left + (v - x0) / (x1 - x0) * (width - left - right)
	sy = lambda v: top + (y1 - v) / (y1 - y0) * (height - top - bottom)

	parts = []

	# y grid lines & labels
	for tick in nice_ticks(y0, y1):
		y = sy(tick)
		parts.append(f'<line x1="{left}" x2="{width - right}" y1="{y:.1f}" y2="{y:.1f}" class="stroke-border"/>')
		parts.append(f'<text x="{left - 8}" y="{y + 4:.1f}" text-anchor="end">{tick:.6g}</text>')

	# x grid lines & labels, the outer labels align to the chart edges
	x_ticks = time_ticks(x0, x1) if time_axis else [(t, f"{t:.6g}") for t in nice_ticks(x0, x1, 6)]
	for i, (value, label) in enumerate(x_ticks):
		x = sx(value)
		anchor = "start" if i == 0 else "end" if i == len(x_ticks) - 1 else "middle"
		parts.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{top}" y2="{height - bottom}" class="stroke-border" stroke-opacity="0.5"/>')
		parts.append(f'<text x="{x:.1f}" y="{height - bottom + 18}" text-anchor="{anchor}">{esc(label)}</text>')

	# the lines, with markers for irregular data
	legend = []
	for i, (label, x, y) in enumerate(lines):
		color = COLORS[i % len(COLORS)]
		x, y = decimate(x, y)
		for run in segments(zip(x, y)):
			points = " ".join(f"{sx(xv):.1f},{sy(yv):.1f}" for xv, yv in run)
			parts.append(f'<polyline fill="none" stroke="{color}" stroke-width="1.6" points="{points}"/>')
		if markers and x.size <= 400:
			parts.extend(f'<circle cx="{sx(xv):.1f}" cy="{sy(yv):.1f}" r="2.6" fill="{color}"/>'
				for xv, yv in zip(x, y) if not np.isnan(yv))
		legend.append(f'<span class="flex items-center gap-1.5"><span class="h-2.5 w-2.5 rounded-sm" '
			f'style="background:{color}"></span>{esc(label)}</span>')

	# axis titles
	parts.append(f'<text x="{(left + width - right) / 2}" y="{height - 6}" text-anchor="middle">{esc(x_label)}</text>')
	parts.append(f'<text transform="translate(14 {(top + height - bottom) / 2}) rotate(-90)" text-anchor="middle">{esc(y_label)}</text>')

	svg = (f'<svg viewBox="0 0 {width} {height}" class="h-auto w-full fill-muted-foreground" font-size="11" '
		f'font-family="IBM Plex Mono, ui-monospace, monospace">{"".join(parts)}</svg>')
	return f'<div class="mb-2 flex flex-wrap gap-4 text-xs">{"".join(legend)}</div>{svg}'


def grid_png(data):
	''' north-up 2d array -> png bytes, viridis colors, NaN transparent '''
	valid = data[~np.isnan(data)]
	lo, hi = (float(valid.min()), float(valid.max())) if valid.size else (0.0, 1.0)
	scaled = np.clip((data - lo) / ((hi - lo) or 1.0), 0, 1)

	# interpolate the color stops
	position = np.nan_to_num(scaled) * (len(VIRIDIS) - 1)
	low = np.minimum(np.floor(position).astype(int), len(VIRIDIS) - 2)
	frac = (position - low)[..., None]
	rgb = VIRIDIS[low] * (1 - frac) + VIRIDIS[low + 1] * frac
	alpha = np.where(np.isnan(data), 0, 255)[..., None]
	rgba = np.concatenate([rgb, alpha], axis=-1).astype(np.uint8)

	# png: signature, header, compressed rows (each starts with filter type 0), end
	rows, cols = data.shape
	raw = b"".join(b"\x00" + rgba[r].tobytes() for r in range(rows))

	def chunk(kind, payload):
		return struct.pack(">I", len(payload)) + kind + payload + struct.pack(">I", zlib.crc32(kind + payload))

	return (b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", struct.pack(">IIBBBBB", cols, rows, 8, 6, 0, 0, 0))
		+ chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b""))



''' ** views ** '''

class Browser:
	''' renders the views of one dss file, temp_dir holds an uploaded copy '''

	def __init__(self, filename, file_id, name=None, temp_dir=None):
		self.filename = filename
		self.id = file_id
		self.name = name or os.path.basename(filename)
		self.temp_dir = temp_dir
		self.dss_file = phl.open(filename)

	def close(self):
		self.dss_file.close()
		if self.temp_dir:
			shutil.rmtree(self.temp_dir, ignore_errors=True)

	def body(self, path=""):
		''' catalog & detail panels, path opens a record (links like /?file=1&path=/A/B/C/D/E/F/) '''
		kind_select = select("kind", [("", "All types")] + [(key, label) for key, (label, _) in RECORD_KINDS.items()])
		return FILE_BODY.format(file_id=self.id, kind_select=kind_select,
			detail=self.record(path) if path else EMPTY_DETAIL)

	def url(self, route, path):
		return f"{route}?file={self.id}&path={quote(str(path))}"

	# -- catalog --

	def filtered_catalog(self, search="", kind=""):
		''' (path, code) pairs of the condensed catalog matching the filters

			search has words that all must match: "B=GAGE" matches part B (partly,
			or the whole part with * ? wild characters), any other word matches
			anywhere in the pathname, like "/GAGE/FLOW/"
		'''
		texts, patterns = [], []
		for word in search.upper().split():
			part, _, value = word.partition("=")
			if part in ("A", "B", "C", "D", "E", "F") and value:
				patterns.append((part, value if any(c in value for c in "*?[") else f"*{value}*"))
			else:
				texts.append(word)

		def matches(path, code):
			return ((not kind or RECORD_KINDS[kind][1](code))
				and all(text in str(path).upper() for text in texts)
				and all(fnmatch.fnmatchcase(getattr(path, p).upper(), pattern) for p, pattern in patterns))

		return [(path, code) for path, code in self.dss_file.catalog(condensed=True, with_types=True) if matches(path, code)]

	def catalog(self, query):
		entries = self.filtered_catalog(query.get("search", ""), query.get("kind", ""))
		if not entries:
			return '<p class="p-6 text-center text-sm text-muted-foreground">No records match the filter</p>'

		rows = []
		for path, code in entries[:MAX_ROWS]:
			label = next((label for label, test in RECORD_KINDS.values() if test(code)), str(code))
			rows.append(f'''<tr class="cursor-pointer border-b transition-colors hover:bg-muted/50" data-path="{esc(path)}" onclick="selectRow(this)"
				hx-get="{self.url("/record", path)}" hx-target="#detail" hx-push-url="{self.url("/", path)}">
				<td class="truncate px-4 py-2 font-mono text-xs" title="{esc(path)}">{esc(path)}</td>
				<td class="px-4 py-2 text-right">{badge(label)}</td></tr>''')

		total = len(entries)
		count = f'<span class="font-mono">{total}</span>'
		shown = f'showing <span class="font-mono">{min(total, MAX_ROWS)}</span> of {count}' if total > MAX_ROWS else f"{count} records"
		# fixed layout: long pathnames end with ... when the side is narrow
		return f'''<table class="w-full table-fixed text-sm"><thead class="sticky top-0 bg-card">
			<tr><th class="h-9 truncate px-4 text-left font-medium text-muted-foreground">Pathname</th>
			<th class="h-9 w-36 truncate px-4 text-right font-medium text-muted-foreground">{shown}</th></tr></thead>
			<tbody>{"".join(rows)}</tbody></table>'''

	# -- record --

	def record(self, path):
		try:
			rec = self.dss_file.read(path)
		except Exception as error:   # show read errors in the page
			return panel("Unable to read record", f'<p class="text-sm text-muted-foreground">{esc(error)}</p>')

		if isinstance(rec, (phl.RegularTs, phl.IrregularTs)):
			body = self.time_series_view(rec)
		elif isinstance(rec, phl.PairedData):
			body = self.paired_view(rec)
		else:
			body = self.grid_view(rec, path)

		title = f'<span class="font-mono text-sm" title="{esc(rec.path)}">{esc(rec.path)}</span>'
		csv_link = (f'<a href="{self.url("/csv", path)}" class="ml-auto inline-flex h-8 items-center gap-1.5 rounded-md border '
			f'px-3 text-xs font-medium shadow-sm hover:bg-accent">{icon("download", "h-3.5 w-3.5")}Download CSV</a>')
		return panel(title, body, badge(type(rec).__name__, outline=True) + csv_link)

	def time_series_view(self, rec):
		series = rec.to_series()
		info = [("Units", rec.unit or "-"), ("Type", rec.type), ("Values", series.size),
			("Interval", rec.interval if isinstance(rec, phl.RegularTs) else rec.path.E),
			("Start", series.index[0] if series.size else "-"), ("End", series.index[-1] if series.size else "-"),
			("Time zone", rec.time_zone or "-"), ("Quality", "yes" if rec.quality is not None else "no")]
		chart = line_chart([(rec.path.C, series.index.asi8 / 1e9, series.values)],
			y_label=f"{rec.path.C} ({rec.unit})", time_axis=True, markers=isinstance(rec, phl.IrregularTs))
		table = data_table(series.to_frame().head(MAX_TABLE_ROWS), series.size)
		return info_grid(info + stats(series.values)) + tabs([("Graph", "line-chart", chart), ("Table", "table", table)])

	def paired_view(self, rec):
		df = rec.to_dataframe()
		info = [("X units", rec.x_unit or "-"), ("Y units", rec.y_unit or "-"), ("X type", rec.x_type or "-"),
			("Y type", rec.y_type or "-"), ("Curves", rec.n_curves), ("Ordinates", rec.x.size),
			("Labels", ", ".join(rec.labels) or "-"), ("Time zone", rec.time_zone or "-")]
		chart = line_chart([(col, rec.x, df[col].values) for col in df.columns],
			x_label=f"{df.index.name} ({rec.x_unit})", y_label=f"{rec.path.C.split('-')[-1]} ({rec.y_unit})")
		table = data_table(df.head(MAX_TABLE_ROWS), len(df))
		return info_grid(info) + tabs([("Graph", "line-chart", chart), ("Table", "table", table)])

	def grid_view(self, rec, path):
		xmin, xmax, ymin, ymax = rec.extent
		info = [("Units", rec.unit or "-"), ("Type", rec.type), ("Grid type", rec.grid_type),
			("Shape", f"{rec.shape[0]} x {rec.shape[1]}"), ("Cell size", f"{rec.cell_size:g}"),
			("Lower left cell", rec.lower_left_cell), ("Extent x", f"{xmin:g} .. {xmax:g}"),
			("Extent y", f"{ymin:g} .. {ymax:g}"), ("Start", rec.start_time or "-"), ("End", rec.end_time or "-"),
			("SRS", rec.srs_name or ("WKT" if rec.srs_wkt else "-")), ("Time zone", rec.time_zone or "-")]

		# the image comes from /grid.png, with a color bar below it
		valid = rec.data[~np.isnan(rec.data)]
		lo, hi = (f"{valid.min():.4g}", f"{valid.max():.4g}") if valid.size else ("-", "-")
		gradient = ", ".join(f"rgb({r:.0f},{g:.0f},{b:.0f})" for r, g, b in VIRIDIS)
		image = f'''<div class="mt-6 space-y-2">
			<img src="{self.url("/grid.png", path)}" alt="grid" class="w-full rounded-md border bg-[repeating-conic-gradient(hsl(var(--muted))_0_25%,transparent_0_50%)] bg-[length:16px_16px]"
				style="image-rendering: pixelated; aspect-ratio: {rec.shape[1]} / {rec.shape[0]}">
			<div class="flex items-center gap-2 font-mono text-xs text-muted-foreground"><span>{lo}</span>
				<div class="h-2.5 flex-1 rounded" style="background: linear-gradient(to right, {gradient})"></div>
				<span>{hi} {esc(rec.unit)}</span></div>
			<p class="text-xs text-muted-foreground">transparent cells are nodata</p></div>'''
		return info_grid(info + stats(rec.data.ravel())) + image

	# -- downloads --

	def grid_image(self, path):
		return grid_png(self.dss_file.read(path).data)

	def csv(self, path):
		rec = self.dss_file.read(path)
		buffer = io.StringIO()
		if isinstance(rec, phl.GriddedData):
			np.savetxt(buffer, rec.data, delimiter=",", fmt="%.6g")
		elif isinstance(rec, phl.PairedData):
			rec.to_dataframe().to_csv(buffer)
		else:
			rec.to_series().to_csv(buffer)
		return buffer.getvalue()


class Workspace:
	''' the open dss files by id, each one is a tab in the page '''

	def __init__(self):
		self.files = {}
		self.next_id = 1

	def add(self, filename, name=None, temp_dir=None):
		browser = Browser(filename, self.next_id, name, temp_dir)
		self.files[browser.id] = browser
		self.next_id += 1
		return browser

	def upload(self, name, stream, size):
		''' save an uploaded file to a temp dir & open it '''
		name = os.path.basename(name) or "upload.dss"
		temp_dir = tempfile.mkdtemp(prefix="dss_browser_")
		filename = os.path.join(temp_dir, name)
		with open(filename, "wb") as out:
			while size > 0:
				data = stream.read(min(size, 1 << 20))
				if not data:
					break
				out.write(data)
				size -= len(data)
		try:
			return self.add(filename, name, temp_dir)
		except Exception:
			shutil.rmtree(temp_dir, ignore_errors=True)
			raise

	def get(self, file_id):
		return self.files.get(int(file_id)) if str(file_id).isdigit() else None

	def close(self, file_id):
		browser = self.files.pop(int(file_id), None) if str(file_id).isdigit() else None
		if browser:
			browser.close()

	def close_all(self):
		for file_id in list(self.files):
			self.close(file_id)

	def page(self, browser=None, path=""):
		''' full page with the file tabs, without a browser it asks to open a file '''
		if browser:
			body = browser.body(path)
		else:
			body = NO_FILE_BODY.format(upload_icon=icon("upload-cloud", "h-10 w-10"), open_icon=icon("folder-open"))
		return PAGE.format(
			title=esc(browser.name if browser else "open a file"), version=phl.__version__,
			file_id=browser.id if browser else "", body=body,
			file_tabs="".join(file_tab(b, b is browser) for b in self.files.values()),
			style=STYLE, head_script=HEAD_SCRIPT, script=SCRIPT,
			logo_icon=icon("database", "h-5 w-5"), open_icon=icon("folder-open"), upload_icon=icon("upload-cloud", "h-10 w-10"),
			sun_icon=icon("sun"), moon_icon=icon("moon"))



''' ** http server ** '''

class Server(HTTPServer):
	# on windows address reuse lets a second server bind a port that is in use
	allow_reuse_address = not sys.platform.startswith("win")


def bind(handler, host, port):
	''' a server on port, or on one of the next PORT_TRIES ports when it is in use '''
	for attempt in range(PORT_TRIES + 1):
		try:
			return Server((host, port + attempt), handler)
		except OSError as error:
			in_use = error.errno in (errno.EADDRINUSE, getattr(errno, "WSAEADDRINUSE", None))
			if not in_use or port == 0:
				raise
			if attempt < PORT_TRIES:
				print(f"port {port + attempt} is in use, trying {port + attempt + 1} ({attempt + 1}/{PORT_TRIES})")
	raise OSError(errno.EADDRINUSE, f"ports {port}-{port + PORT_TRIES} are not available, aborting")


def make_server(filenames=(), host="127.0.0.1", port=8765):
	workspace = Workspace()
	for filename in filenames:
		workspace.add(filename)

	class Handler(BaseHTTPRequestHandler):

		def query(self):
			url = urlparse(self.path)
			return url.path, {k: v[0] for k, v in parse_qs(url.query, keep_blank_values=True).items()}

		def do_GET(self):
			route, query = self.query()
			path = query.get("path", "")
			browser = workspace.get(query.get("file", ""))

			try:
				if route == "/":
					if browser is None and workspace.files:   # unknown or no file id: first file
						browser, path = next(iter(workspace.files.values())), ""
					self.send(workspace.page(browser, path))
				elif route == "/ping":
					self.send("ok", "text/plain")
				elif browser is None:   # the other routes need an open file
					self.send("file is not open", "text/plain", status=404)
				elif route == "/catalog":
					self.send(browser.catalog(query))
				elif route == "/record":
					self.send(browser.record(path))
				elif route == "/grid.png":
					self.send(browser.grid_image(path), "image/png")
				elif route == "/csv":
					name = "_".join(p for p in path.split("/") if p) or "record"
					self.send(browser.csv(path), "text/csv",
						{"Content-Disposition": f'attachment; filename="{name}.csv"'})
				else:
					self.send("not found", "text/plain", status=404)
			except Exception as error:
				self.send(f"error: {error}", "text/plain", status=500)

		def do_POST(self):
			route, query = self.query()
			try:
				if route == "/open":
					size = int(self.headers.get("Content-Length", 0))
					self.send(str(workspace.upload(query.get("name", ""), self.rfile, size).id), "text/plain")
				elif route == "/close":
					workspace.close(query.get("file", ""))
					self.send("ok", "text/plain")
				else:
					self.send("not found", "text/plain", status=404)
			except Exception as error:   # mostly files that are not dss files
				self.send(f"{error}", "text/plain", status=400)

		def send(self, body, content_type="text/html; charset=utf-8", headers=None, status=200):
			body = body.encode("utf-8") if isinstance(body, str) else body
			self.send_response(status)
			self.send_header("Content-Type", content_type)
			self.send_header("Content-Length", str(len(body)))
			for key, value in (headers or {}).items():
				self.send_header(key, value)
			self.end_headers()
			self.wfile.write(body)

		def log_message(self, format, *args):
			pass

	try:
		server = bind(Handler, host, port)
	except OSError:
		workspace.close_all()
		raise
	server.workspace = workspace
	return server


def main():
	parser = argparse.ArgumentParser(description="browse dss files in the web browser")
	parser.add_argument("filenames", nargs="*", help="dss files to open, more can be opened from the page")
	parser.add_argument("--host", default="127.0.0.1")
	parser.add_argument("--port", type=int, default=8765)
	parser.add_argument("--no-browser", action="store_true", help="do not open the web browser")
	args = parser.parse_args()

	try:
		server = make_server(args.filenames, args.host, args.port)
	except OSError as error:
		print(error.strerror or error, file=sys.stderr)
		return 1
	url = f"http://{args.host}:{server.server_address[1]}/"
	print(f"serving {', '.join(args.filenames) or 'no file (open one in the page)'} at {url}  (ctrl+c to stop)")

	if not args.no_browser:
		webbrowser.open(url)
	try:
		server.serve_forever()
	except KeyboardInterrupt:
		pass
	finally:
		server.server_close()
		server.workspace.close_all()



''' ** icons ** '''

# svg paths of remix icons (https://remixicon.com, apache 2.0)
ICONS = {
	"database": "M5 12.5C5 12.8134 5.46101 13.3584 6.53047 13.8931C7.91405 14.5849 9.87677 15 12 15C14.1232 15 16.0859 14.5849 17.4695 13.8931C18.539 13.3584 19 12.8134 19 12.5V10.3287C17.35 11.3482 14.8273 12 12 12C9.17273 12 6.64996 11.3482 5 10.3287V12.5ZM19 15.3287C17.35 16.3482 14.8273 17 12 17C9.17273 17 6.64996 16.3482 5 15.3287V17.5C5 17.8134 5.46101 18.3584 6.53047 18.8931C7.91405 19.5849 9.87677 20 12 20C14.1232 20 16.0859 19.5849 17.4695 18.8931C18.539 18.3584 19 17.8134 19 17.5V15.3287ZM3 17.5V7.5C3 5.01472 7.02944 3 12 3C16.9706 3 21 5.01472 21 7.5V17.5C21 19.9853 16.9706 22 12 22C7.02944 22 3 19.9853 3 17.5ZM12 10C14.1232 10 16.0859 9.58492 17.4695 8.89313C18.539 8.3584 19 7.81342 19 7.5C19 7.18658 18.539 6.6416 17.4695 6.10687C16.0859 5.41508 14.1232 5 12 5C9.87677 5 7.91405 5.41508 6.53047 6.10687C5.46101 6.6416 5 7.18658 5 7.5C5 7.81342 5.46101 8.3584 6.53047 8.89313C7.91405 9.58492 9.87677 10 12 10Z",
	"folder-open": "M3 21C2.44772 21 2 20.5523 2 20V4C2 3.44772 2.44772 3 3 3H10.4142L12.4142 5H20C20.5523 5 21 5.44772 21 6V9H19V7H11.5858L9.58579 5H4V16.998L5.5 11H22.5L20.1894 20.2425C20.0781 20.6877 19.6781 21 19.2192 21H3ZM19.9384 13H7.06155L5.56155 19H18.4384L19.9384 13Z",
	"arrow-down": "M11.9999 13.1714L16.9497 8.22168L18.3639 9.63589L11.9999 15.9999L5.63599 9.63589L7.0502 8.22168L11.9999 13.1714Z",
	"check": "M9.9997 15.1709L19.1921 5.97852L20.6063 7.39273L9.9997 17.9993L3.63574 11.6354L5.04996 10.2212L9.9997 15.1709Z",
	"close": "M11.9997 10.5865L16.9495 5.63672L18.3637 7.05093L13.4139 12.0007L18.3637 16.9504L16.9495 18.3646L11.9997 13.4149L7.04996 18.3646L5.63574 16.9504L10.5855 12.0007L5.63574 7.05093L7.04996 5.63672L11.9997 10.5865Z",
	"download": "M13 10H18L12 16L6 10H11V3H13V10ZM4 19H20V12H22V20C22 20.5523 21.5523 21 21 21H3C2.44772 21 2 20.5523 2 20V12H4V19Z",
	"line-chart": "M5 3V19H21V21H3V3H5ZM20.2929 6.29289L21.7071 7.70711L16 13.4142L13 10.415L8.70711 14.7071L7.29289 13.2929L13 7.58579L16 10.585L20.2929 6.29289Z",
	"sun": "M12 18C8.68629 18 6 15.3137 6 12C6 8.68629 8.68629 6 12 6C15.3137 6 18 8.68629 18 12C18 15.3137 15.3137 18 12 18ZM12 16C14.2091 16 16 14.2091 16 12C16 9.79086 14.2091 8 12 8C9.79086 8 8 9.79086 8 12C8 14.2091 9.79086 16 12 16ZM11 1H13V4H11V1ZM11 20H13V23H11V20ZM3.51472 4.92893L4.92893 3.51472L7.05025 5.63604L5.63604 7.05025L3.51472 4.92893ZM16.9497 18.364L18.364 16.9497L20.4853 19.0711L19.0711 20.4853L16.9497 18.364ZM19.0711 3.51472L20.4853 4.92893L18.364 7.05025L16.9497 5.63604L19.0711 3.51472ZM5.63604 16.9497L7.05025 18.364L4.92893 20.4853L3.51472 19.0711L5.63604 16.9497ZM23 11V13H20V11H23ZM4 11V13H1V11H4Z",
	"moon": "M10 7C10 10.866 13.134 14 17 14C18.9584 14 20.729 13.1957 21.9995 11.8995C22 11.933 22 11.9665 22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C12.0335 2 12.067 2 12.1005 2.00049C10.8043 3.27098 10 5.04157 10 7ZM4 12C4 16.4183 7.58172 20 12 20C15.0583 20 17.7158 18.2839 19.062 15.7621C18.3945 15.9187 17.7035 16 17 16C12.0294 16 8 11.9706 8 7C8 6.29648 8.08133 5.60547 8.2379 4.938C5.71611 6.28423 4 8.9417 4 12Z",
	"table": "M13 10V14H19V10H13ZM11 10H5V14H11V10ZM13 19H19V16H13V19ZM11 19V16H5V19H11ZM13 5V8H19V5H13ZM11 5H5V8H11V5ZM4 3H20C20.5523 3 21 3.44772 21 4V20C21 20.5523 20.5523 21 20 21H4C3.44772 21 3 20.5523 3 20V4C3 3.44772 3.44772 3 4 3Z",
	"upload-cloud": "M12 12.5858L16.2426 16.8284L14.8284 18.2426L13 16.415V22H11V16.413L9.17157 18.2426L7.75736 16.8284L12 12.5858ZM12 2C15.5934 2 18.5544 4.70761 18.9541 8.19395C21.2858 8.83154 23 10.9656 23 13.5C23 16.3688 20.8036 18.7246 18.0006 18.9776L18.0009 16.9644C19.6966 16.7214 21 15.2629 21 13.5C21 11.567 19.433 10 17.5 10C17.2912 10 17.0867 10.0183 16.8887 10.054C16.9616 9.7142 17 9.36158 17 9C17 6.23858 14.7614 4 12 4C9.23858 4 7 6.23858 7 9C7 9.36158 7.03838 9.7142 7.11205 10.0533C6.91331 10.0183 6.70879 10 6.5 10C4.567 10 3 11.567 3 13.5C3 15.2003 4.21241 16.6174 5.81986 16.934L6.00005 16.9646L6.00039 18.9776C3.19696 18.7252 1 16.3692 1 13.5C1 10.9656 2.71424 8.83154 5.04648 8.19411C5.44561 4.70761 8.40661 2 12 2Z",
}


if __name__ == "__main__":
	sys.exit(main())
