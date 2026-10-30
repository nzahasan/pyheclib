#!/usr/bin/env python3
'''
	dss_browser: browse dss files in the web browser.

	    dss_browser [file.dss ...] [--port 8765] [--no-browser]

	A single file tool using the python built in http server. The page uses
	htmx for interaction, shadcn/ui styling (tailwind + shadcn theme tokens,
	with the fluent ui brand blues for selection, tags & tabs) & uplot charts,
	all loaded from cdns, a warning shows when one of them can not be loaded.
	More files can be opened from the page (open button or drag & drop),
	every open file gets a tab. Records are shown as a graph (uplot charts,
	png images for grids) and as a table, every record can be downloaded as
	csv.

	The file reads top to bottom: page templates, html helpers, charts, the
	views of a file, the http server & the svg icons at the end.
'''

import argparse
import errno
import fnmatch
import html
import io
import json
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
MAX_CHART_POINTS = 5000
PORT_TRIES = 3          # next ports tried when the port is in use

UPLOT_URL = "https://unpkg.com/uplot@1.6.32/dist/uPlot.iife.min.js"
UPLOT_CSS_URL = "https://unpkg.com/uplot@1.6.32/dist/uPlot.min.css"

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
<script>{head_script}</script>
<style>{style}</style>
<link rel="stylesheet" href="{uplot_css_url}" onerror="cdnFailed('uPlot')">
<script src="https://unpkg.com/htmx.org@2.0.4" onerror="cdnFailed('htmx')"></script>
<script src="https://cdn.tailwindcss.com" onerror="cdnFailed('Tailwind')"></script>
<script>if (window.tailwind) tailwind.config = TAILWIND_CONFIG;</script>
<script src="{uplot_url}" onerror="cdnFailed('uPlot')"></script>
</head>
<body data-file="{file_id}" class="flex h-screen flex-col overflow-hidden bg-background text-foreground antialiased">
<div id="cdn-warning" role="alert" hidden></div>
<header class="shrink-0 border-b">
	<div class="flex h-14 items-center gap-3 px-6">
		<div class="flex shrink-0 items-center gap-2 font-semibold tracking-tight">{logo_icon}DSS BROWSER</div>
		<nav class="flex min-w-0 items-center gap-1 overflow-x-auto rounded-lg bg-muted p-1 text-muted-foreground">{file_tabs}
			<button type="button" onclick="picker.click()" title="open dss files, or drop them on the page"
				class="inline-flex items-center gap-1.5 whitespace-nowrap rounded-md px-3 py-1 text-sm font-medium text-brand hover:bg-background">{open_icon}Open</button>
		</nav>
		<input id="picker" type="file" accept=".dss" multiple hidden onchange="openFiles(this.files)">
		<span class="ml-auto shrink-0 text-xs text-muted-foreground">pyheclib <span class="font-mono">{version}</span></span>
		<button type="button" onclick="toggleTheme()" title="toggle dark / light theme"
			class="inline-flex h-8 w-8 shrink-0 items-center justify-center rounded-md border text-brand shadow-sm hover:bg-accent">
			<span class="dark:hidden">{moon_icon}</span><span class="hidden dark:inline">{sun_icon}</span></button>
	</div>
</header>
{body}

<div id="drop" class="fixed inset-4 z-40 hidden items-center justify-center rounded-md border-2 border-dashed border-brand bg-background/80">
	<div class="flex flex-col items-center gap-3 text-brand">{upload_icon}
		<div class="font-semibold tracking-tight">Drop dss files to open them</div></div>
</div>
<div id="opening" class="pointer-events-none fixed inset-0 z-40 hidden items-center justify-center">
	<div class="flex items-center gap-3 rounded-md border bg-card px-5 py-4 text-sm font-medium shadow-lg">
		<span class="h-5 w-5 animate-spin rounded-full border-2 border-brand border-t-transparent"></span>
		<span id="opening-text">Opening...</span></div>
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
			class="inline-flex h-9 items-center gap-2 rounded-md bg-primary px-4 text-sm font-medium text-primary-foreground shadow hover:opacity-90">{open_icon}Open file</button>
	</div>
</main>'''

STYLE = '''
:root {
	--background: 0 0% 100%; --foreground: 240 10% 3.9%; --card: 0 0% 100%; --card-foreground: 240 10% 3.9%;
	--secondary: 240 4.8% 95.9%;
	--secondary-foreground: 240 5.9% 10%; --muted: 240 4.8% 95.9%; --muted-foreground: 240 3.8% 46.1%;
	--accent: 240 4.8% 95.9%; --accent-foreground: 240 5.9% 10%; --border: 240 5.9% 90%;
	--input: 240 5.9% 90%; --ring: 240 5.9% 10%; --radius: 0.5rem;
	/* fluent ui brand colors: buttons, selected row, its light accent for hover, tags & the active tab */
	--brand: #0f6cbd; --brand-soft: #ebf3fc; --brand-text: #115ea3; --brand-stroke: #b4d6fa; --brand-line: #0f6cbd;
	color-scheme: light;
}
.dark {
	--background: 240 10% 3.9%; --foreground: 0 0% 98%; --card: 240 10% 3.9%; --card-foreground: 0 0% 98%;
	--secondary: 240 3.7% 15.9%;
	--secondary-foreground: 0 0% 98%; --muted: 240 3.7% 15.9%; --muted-foreground: 240 5% 64.9%;
	--accent: 240 3.7% 15.9%; --accent-foreground: 0 0% 98%; --border: 240 3.7% 15.9%;
	--input: 240 3.7% 15.9%; --ring: 240 4.9% 83.9%;
	--brand: #115ea3; --brand-soft: #082338; --brand-text: #62abf5; --brand-stroke: #0e4775; --brand-line: #479ef5;
	color-scheme: dark;
}
body { font-family: "IBM Plex Sans", ui-sans-serif, system-ui, sans-serif; margin: 0; }
#cdn-warning { padding: 8px 24px; font-size: 13px; background: #fff4ce; color: #4d3b00; border-bottom: 1px solid #f9e2ae; }
.htmx-indicator { opacity: 0; transition: opacity 200ms; }
.htmx-request .htmx-indicator, .htmx-request.htmx-indicator { opacity: 1; }
tr.catalog-row:hover { background: var(--brand-soft); }
tr.selected, tr.selected:hover { background: var(--brand); color: #fff; }
.badge-brand { background: var(--brand-soft); color: var(--brand-text); border: 1px solid var(--brand-stroke); }
tr.selected .badge { background: rgb(255 255 255 / 0.2); color: #fff; border-color: transparent; }
thead th { box-shadow: inset 0 -1px 0 hsl(var(--border)); }   /* collapsed borders do not move with sticky headers */
[role="option"]:hover { background: var(--brand-soft); }   /* same as the catalog rows */
[role="option"][aria-checked="true"] { color: var(--brand-line); }
[role="option"][aria-checked="false"] .check { visibility: hidden; }
[aria-selected="true"] { background: hsl(var(--background)); color: var(--brand-line); box-shadow: inset 0 0 0 1px var(--brand-line), 0 1px 2px rgb(0 0 0 / 0.08); }   /* inset: the border takes no room */
.uplot { font-family: inherit; width: 100% !important; }
.uplot .u-legend { font-size: 12px; color: hsl(var(--foreground)); }
.uplot .u-legend .u-value { font-family: "IBM Plex Mono", ui-monospace, monospace; }   /* values under the cursor */
'''

# runs before the first paint & before the cdn scripts
HEAD_SCRIPT = '''
// theme: saved choice, else the system setting
if ((localStorage.getItem("dss-theme") || (matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")) === "dark")
	document.documentElement.classList.add("dark");

// cdn scripts & styles that can not be loaded, shown in the warning bar at the top
const missing = [];
function cdnFailed(name) {
	if (!missing.includes(name)) missing.push(name);
	showMissing();
}
function showMissing() {
	const bar = document.getElementById("cdn-warning");
	if (!bar || !missing.length) return;
	bar.textContent = `Unable to load ${missing.join(", ")} from the CDN, the page may not look or work right. `
		+ "Check the internet connection and reload the page.";
	bar.hidden = false;
}
document.addEventListener("DOMContentLoaded", showMissing);

// shadcn colors from the theme tokens in the style
const TAILWIND_CONFIG = { darkMode: "class", theme: { extend: { colors: {
	border: "hsl(var(--border))", input: "hsl(var(--input))", ring: "hsl(var(--ring))",
	background: "hsl(var(--background))", foreground: "hsl(var(--foreground))",
	primary: { DEFAULT: "var(--brand)", foreground: "#fff" }, brand: "var(--brand-line)",
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
	drawCharts();
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

// copy the full pathname of the record, a check shows for a moment
async function copyPath(button) {
	await navigator.clipboard.writeText(button.dataset.path);
	const [copy, done] = button.querySelectorAll("svg");
	copy.classList.add("hidden"); done.classList.remove("hidden");
	setTimeout(() => { copy.classList.remove("hidden"); done.classList.add("hidden"); }, 1200);
}

// show or hide an overlay
function show(element, visible) {
	element.classList.toggle("hidden", !visible);
	element.classList.toggle("flex", visible);
}

// open files: upload them, the server opens a copy, a spinner shows until the page of the file loads
const drop = document.getElementById("drop");
const opening = document.getElementById("opening");
async function openFiles(files) {
	let opened = null;
	for (const file of files) {
		document.getElementById("opening-text").textContent = `Opening ${file.name}...`;
		show(opening, true);
		const response = await fetch("/open?name=" + encodeURIComponent(file.name), { method: "POST", body: file });
		const text = await response.text();
		if (response.ok) opened = text;
		else alert(`Unable to open ${file.name}\\n${text}`);
	}
	if (opened !== null) location = "/?file=" + opened;
	else show(opening, false);
}
async function closeFile(id) {
	await fetch("/close?file=" + id, { method: "POST" });
	if (String(id) === currentFile) location = "/";
	else location.reload();
}

let dragDepth = 0;
document.addEventListener("dragenter", event => {
	if (event.dataTransfer.types.includes("Files") && ++dragDepth === 1) show(drop, true);
});
document.addEventListener("dragleave", () => {
	if (dragDepth > 0 && --dragDepth === 0) show(drop, false);
});
document.addEventListener("dragover", event => event.preventDefault());
document.addEventListener("drop", event => {
	event.preventDefault();
	dragDepth = 0;
	show(drop, false);
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
document.addEventListener("htmx:afterSwap", () => {
	document.querySelectorAll(".tabs").forEach(applyTabs);
	drawCharts();
});

// uplot charts from the json in data-chart, drawn again for a new theme, sized to their box
const CHART_HEIGHT = 300;
const charts = new WeakMap();
const resizer = new ResizeObserver(entries => entries.forEach(({ target }) => {
	if (target.clientWidth) charts.get(target)?.setSize({ width: target.clientWidth, height: CHART_HEIGHT });
}));
function drawCharts() {
	if (window.uPlot) document.querySelectorAll(".chart[data-chart]").forEach(drawChart);
}
function drawChart(box) {
	charts.get(box)?.destroy();
	const spec = JSON.parse(box.dataset.chart);
	const css = getComputedStyle(document.documentElement);
	const color = name => `hsl(${css.getPropertyValue("--" + name).trim()})`;   // canvas colors from the theme tokens
	const axis = label => ({ label, size: 60, stroke: color("muted-foreground"),
		font: '11px "IBM Plex Mono", monospace', labelFont: '12px "IBM Plex Sans", sans-serif',
		grid: { stroke: color("border"), width: 1 }, ticks: { stroke: color("border"), width: 1 } });
	const options = {
		width: box.clientWidth, height: CHART_HEIGHT,
		scales: { x: { time: spec.time } },
		tzDate: seconds => uPlot.tzDate(new Date(seconds * 1e3), "Etc/UTC"),   // dss times have no time zone
		series: [{ label: spec.xLabel || (spec.time ? "Time" : "x") }, ...spec.series.map(s => ({
			label: s.label, stroke: s.color, width: 1.6, points: spec.points ? { show: true, size: 5, fill: s.color } : {} }))],
		axes: [axis(spec.xLabel), axis(spec.yLabel)],
	};
	charts.set(box, new uPlot(options, [spec.x, ...spec.series.map(s => s.y)], box));
	resizer.observe(box);
}
drawCharts();

// while the server can not be reached: blur the page & turn it off (inert: no clicks, no typing)
const offline = document.getElementById("offline");
async function ping() {
	let up = false;
	try {
		up = (await fetch("/ping", { cache: "no-store", signal: AbortSignal.timeout(2000) })).ok;
	} catch (error) {}
	const wasDown = !offline.classList.contains("hidden");
	show(offline, !up);
	for (const element of document.body.children) {
		if (element !== offline) element.inert = !up;
	}
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
	style = "border text-foreground" if outline else "badge-brand"
	return f'<span class="badge inline-flex items-center rounded-md px-2 py-0.5 text-xs font-medium whitespace-nowrap shrink-0 {style}">{esc(text)}</span>'


def panel(title, body, extra="", lead=""):
	''' fills the detail side, the body scrolls under a header as high as the catalog search bar '''
	return f'''<div class="flex h-16 shrink-0 items-center gap-2 border-b px-5">{lead}
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
		class="relative flex cursor-default select-none items-center whitespace-nowrap rounded-sm py-1.5 pl-2 pr-8 text-sm">
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


def json_values(values):
	''' floats for json, NaN as null: uplot breaks the line at missing values '''
	return [None if math.isnan(v) else v for v in np.asarray(values, dtype=float).tolist()]


def line_chart(lines, x_label="", y_label="", time_axis=False, markers=False):
	''' lines: [(label, x float array, y array)] sharing one x, epoch seconds for time axes, the page draws them with uplot '''
	x = np.asarray(lines[0][1], dtype=float)
	ys = [np.asarray(y, dtype=float) for _, _, y in lines]
	if not x.size or all(np.isnan(y).all() for y in ys):
		return '<p class="text-sm text-muted-foreground">no values to plot</p>'
	if len(ys) == 1:   # curves sharing x (paired data) are short, only a single line is thinned
		x, y = decimate(x, ys[0])
		ys = [y]

	spec = {"time": time_axis, "points": markers, "xLabel": x_label, "yLabel": y_label, "x": json_values(x),
		"series": [{"label": label, "color": COLORS[i % len(COLORS)], "y": json_values(y)}
			for i, ((label, _, _), y) in enumerate(zip(lines, ys))]}
	return f'<div class="chart" data-chart="{esc(json.dumps(spec))}"></div>'


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
			rows.append(f'''<tr class="catalog-row cursor-pointer border-b transition-colors" data-path="{esc(path)}" onclick="selectRow(this)"
				hx-get="{self.url("/record", path)}" hx-target="#detail" hx-push-url="{self.url("/", path)}">
				<td class="truncate px-4 py-2 font-mono text-xs" title="{esc(path)}">{esc(path)}</td>
				<td class="px-4 py-2 text-right">{badge(label)}</td></tr>''')

		total = len(entries)
		count = f'<span class="font-mono">{total}</span>'
		shown = f'showing <span class="font-mono">{min(total, MAX_ROWS)}</span> of {count}' if total > MAX_ROWS else f"{count} records"
		# fixed layout: long pathnames end with ... when the side is narrow
		return f'''<table class="w-full table-fixed text-sm"><thead class="sticky top-0 bg-muted">
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
		copy = (f'<button type="button" title="Copy path" data-path="{esc(rec.path)}" onclick="copyPath(this)" class="inline-flex h-7 w-7 '
			f'shrink-0 items-center justify-center rounded-md text-brand hover:bg-accent">'
			f'{icon("copy", "h-3.5 w-3.5")}{icon("check", "h-3.5 w-3.5 hidden")}</button>')
		csv_link = (f'<a href="{self.url("/csv", path)}" class="ml-auto inline-flex h-8 shrink-0 items-center gap-1.5 whitespace-nowrap '
			f'rounded-md border px-3 text-xs font-medium text-brand shadow-sm hover:bg-accent">{icon("download", "h-3.5 w-3.5")}Download CSV</a>')
		return panel(title, body, badge(type(rec).__name__, outline=True) + csv_link, lead=copy)

	def time_series_view(self, rec):
		series = rec.to_series()
		info = [("Units", rec.unit or "-"), ("Type", rec.type), ("Values", series.size),
			("Interval", rec.interval if isinstance(rec, phl.RegularTs) else rec.path.E),
			("Start", series.index[0] if series.size else "-"), ("End", series.index[-1] if series.size else "-"),
			("Time zone", rec.time_zone or "-"), ("Quality", "yes" if rec.quality is not None else "no")]
		chart = line_chart([(rec.path.C, series.index.asi8 / 1e9, series.values)],
			x_label=f"Time ({rec.time_zone})" if rec.time_zone else "Time", y_label=f"{rec.path.C} ({rec.unit})", time_axis=True, markers=isinstance(rec, phl.IrregularTs))
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
			uplot_url=UPLOT_URL, uplot_css_url=UPLOT_CSS_URL,
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
	"copy": "M6.9998 6V3C6.9998 2.44772 7.44752 2 7.9998 2H19.9998C20.5521 2 20.9998 2.44772 20.9998 3V17C20.9998 17.5523 20.5521 18 19.9998 18H16.9998V20.9991C16.9998 21.5519 16.5499 22 15.993 22H4.00666C3.45059 22 3 21.5554 3 20.9991L3.0026 7.00087C3.0027 6.44811 3.45264 6 4.00942 6H6.9998ZM5.00242 8L5.00019 20H14.9998V8H5.00242ZM8.9998 6H16.9998V16H18.9998V4H8.9998V6Z",
	"download": "M13 10H18L12 16L6 10H11V3H13V10ZM4 19H20V12H22V20C22 20.5523 21.5523 21 21 21H3C2.44772 21 2 20.5523 2 20V12H4V19Z",
	"line-chart": "M5 3V19H21V21H3V3H5ZM20.2929 6.29289L21.7071 7.70711L16 13.4142L13 10.415L8.70711 14.7071L7.29289 13.2929L13 7.58579L16 10.585L20.2929 6.29289Z",
	"sun": "M12 18C8.68629 18 6 15.3137 6 12C6 8.68629 8.68629 6 12 6C15.3137 6 18 8.68629 18 12C18 15.3137 15.3137 18 12 18ZM12 16C14.2091 16 16 14.2091 16 12C16 9.79086 14.2091 8 12 8C9.79086 8 8 9.79086 8 12C8 14.2091 9.79086 16 12 16ZM11 1H13V4H11V1ZM11 20H13V23H11V20ZM3.51472 4.92893L4.92893 3.51472L7.05025 5.63604L5.63604 7.05025L3.51472 4.92893ZM16.9497 18.364L18.364 16.9497L20.4853 19.0711L19.0711 20.4853L16.9497 18.364ZM19.0711 3.51472L20.4853 4.92893L18.364 7.05025L16.9497 5.63604L19.0711 3.51472ZM5.63604 16.9497L7.05025 18.364L4.92893 20.4853L3.51472 19.0711L5.63604 16.9497ZM23 11V13H20V11H23ZM4 11V13H1V11H4Z",
	"moon": "M10 7C10 10.866 13.134 14 17 14C18.9584 14 20.729 13.1957 21.9995 11.8995C22 11.933 22 11.9665 22 12C22 17.5228 17.5228 22 12 22C6.47715 22 2 17.5228 2 12C2 6.47715 6.47715 2 12 2C12.0335 2 12.067 2 12.1005 2.00049C10.8043 3.27098 10 5.04157 10 7ZM4 12C4 16.4183 7.58172 20 12 20C15.0583 20 17.7158 18.2839 19.062 15.7621C18.3945 15.9187 17.7035 16 17 16C12.0294 16 8 11.9706 8 7C8 6.29648 8.08133 5.60547 8.2379 4.938C5.71611 6.28423 4 8.9417 4 12Z",
	"table": "M13 10V14H19V10H13ZM11 10H5V14H11V10ZM13 19H19V16H13V19ZM11 19V16H5V19H11ZM13 5V8H19V5H13ZM11 5H5V8H11V5ZM4 3H20C20.5523 3 21 3.44772 21 4V20C21 20.5523 20.5523 21 20 21H4C3.44772 21 3 20.5523 3 20V4C3 3.44772 3.44772 3 4 3Z",
	"upload-cloud": "M12 12.5858L16.2426 16.8284L14.8284 18.2426L13 16.415V22H11V16.413L9.17157 18.2426L7.75736 16.8284L12 12.5858ZM12 2C15.5934 2 18.5544 4.70761 18.9541 8.19395C21.2858 8.83154 23 10.9656 23 13.5C23 16.3688 20.8036 18.7246 18.0006 18.9776L18.0009 16.9644C19.6966 16.7214 21 15.2629 21 13.5C21 11.567 19.433 10 17.5 10C17.2912 10 17.0867 10.0183 16.8887 10.054C16.9616 9.7142 17 9.36158 17 9C17 6.23858 14.7614 4 12 4C9.23858 4 7 6.23858 7 9C7 9.36158 7.03838 9.7142 7.11205 10.0533C6.91331 10.0183 6.70879 10 6.5 10C4.567 10 3 11.567 3 13.5C3 15.2003 4.21241 16.6174 5.81986 16.934L6.00005 16.9646L6.00039 18.9776C3.19696 18.7252 1 16.3692 1 13.5C1 10.9656 2.71424 8.83154 5.04648 8.19411C5.44561 4.70761 8.40661 2 12 2Z",
}


if __name__ == "__main__":
	sys.exit(main())
