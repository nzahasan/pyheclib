# DSS viewer

The DSS viewer lets you look inside DSS files in your web browser. It runs on your own
computer and needs nothing besides pyheclib.

![DSS viewer](../images/dss_browser.png)

## Get it

The viewer is a single script, `tools/dss_browser.py`, in the
[GitHub repository](https://github.com/nzahasan/pyheclib/tree/main/tools).
Download it, or clone the repository:

```bash
git clone https://github.com/nzahasan/pyheclib
cd pyheclib
```

## Start it

```bash
python3 tools/dss_browser.py example.dss
```

The viewer opens in your web browser at `http://127.0.0.1:8765/`.
Press `Ctrl+C` in the terminal to stop it.

You can open more than one file:

```bash
python3 tools/dss_browser.py basin.dss radar.dss
```

Options:

| Option | Default | Meaning |
|---|---|---|
| `--port` | `8765` | port to serve on |
| `--host` | `127.0.0.1` | address to serve on |
| `--no-browser` | off | do not open the web browser for you |

## Use it

- **Open files**: use the open button or drag a `.dss` file onto the page. Each file gets its own tab.
- **Find records**: filter the list by text, by record type, or by pathname parts with `*`.
- **View a record**: click a record to see its metadata, simple statistics, a chart
  (or an image for grids) and a table of the data.
- **Download**: save any record as a CSV file.
- **Share a link**: each record has its own address, like `/?path=/A/B/C/D/E/F/`.

If you stop the server, the page fades out. It reconnects when the server starts again.

## Try it with the example file

The repository has an example file with every record type:

```bash
python3 tools/dss_browser.py examples/example.dss
```
