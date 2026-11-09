# The header contract

A story may open with a **header band**: a window of a real seismic section with its
interpreted surfaces, drawn by `runtime/js/horizon-band.js` in the page's tokens, in place
of the procedural horizon motif. The story supplies one JSON file in this contract and
names it in the front matter:

```yaml
horizon: { data: header, highlight: Hugin Fm top, height: 150, label: true }
data:
  header: data/header.json
```

`data` names the dataset; `highlight` is the surface drawn in the highlight colour
(default: the file's own `highlight`); `height` is the band's height in css pixels (80 to
400, default 150), reserved in the layout so nothing shifts when the data arrive; `label`
turns the one-line label under the band off; `palette` is `shale` (default: neutral,
positive lobes dark, negative light) or `fjord` (each reflector down a trace takes the next
ink in turn from the saturated fjord and cobalt steps, so the layers alternate in colour;
seismic does not do that, a header may). A hero at the minimum height with the fade, no
label and the fjord palette is the house setting. The build copies the file to `data/<name>.json`
in the site and the page fetches it after first paint. The appendix gains a "Header band"
source line with the attribution, the source file, and the confidence of what is shown.

## The file

| Key | Type | Meaning |
|---|---|---|
| `kind` | `"header"` | required |
| `attribution` | string | required; who owns the data and on what terms (Idiom `DATASETS.md` line) |
| `label` | string | one line drawn under the band: what and where |
| `source_file` | string | the volume the section came from |
| `domain` | object | `vertical` (`time` or `depth`), `vertical_unit`, `quantity`, `quantity_unit` |
| `polarity` | string | `normal`, `reverse` or `unknown` |
| `n_traces`, `n_samples` | int | the window's shape |
| `samples` | number[] | the vertical axis, length `n_samples` |
| `amp_clip` | number | the amplitude that maps to 127 (the 99th percentile is usual) |
| `amp_b64` | string | base64 of int8 amplitudes, row per trace, `n_traces` x `n_samples` |
| `highlight` | string | the default surface to highlight |
| `surfaces` | array | `{label, time: number or null per trace, cover}` shallow to deep; null where no pick |
| `notes` | string[] | anything the reader should know; the first few may be shown by a producer's own pages |

Amplitudes are relative and the band never claims otherwise. The surfaces are the picks at
the section's traces, drawn where they exist and left out where they do not; a producer
must not smooth or infill them.

## Producers

`seismic_art.header.header_payload` (github.com/AdmcCarthy/seismic_art) writes this contract
from any `seismic_lib` section and horizons; `examples/demo/make_data.py` writes a small
synthetic one for the demo. A story keeps its producer in its own `scripts/`, as it keeps
every other extract.

## Size

A Volve inline of 640 traces over 800 ms is about 230 kB as JSON. That is why the file is
fetched rather than inlined in the page payload: the hero paints at once with its height
reserved, and the band follows.
