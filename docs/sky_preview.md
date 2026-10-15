# Target sky preview

The Proposed observation page offers an optional Sky preview below RA/Dec.
It posts only coordinate fields and target kind to `/sky-preview`. This route
uses the same coordinate validator as assessment, without running an assessment
or querying Archive/Queue. Only fixed targets are supported. Other scientific
inputs are not required for preview.

The returned view embeds CDS Aladin Lite v3 from its official `api/v3/latest`
endpoint and requests the `P/DSS2/color` optical survey. These external resources
load only on explicit preview activation; normal form use needs neither.
Aladin retains its logo and attribution. See https://aladin.cds.unistra.fr/AladinLite/doc/
for the library's GPL-3.0 licensing and embedding terms. The upstream latest
endpoint can change independently of this application.

The iframe separates viewer layout/styles from the form; it permits scripts and
same-origin access required by the viewer and is not a security boundary against
the upstream library. No target name, scientific requirements or report data is
sent to the viewer. Survey tile requests reveal the region being viewed to the
imagery service. Network and WebGL availability are required.

The cyan catalogue marker identifies the validated input position. The reticle
marks the current view centre and can move away from the target while panning.
Reset view returns to the input position at 0.25 degree field width. This is an
initial viewing scale, not an ALMA beam or scientific search radius.

Editing coordinates removes the previous preview. Closing/reopening retries
loading. Failure does not disable form validation or assessment. The preview
never writes coordinates back into the form or supplies duplication evidence.

## Report Sky view

The report explorer has a horizontal two-page gallery: Charts retains the
Position/Frequency panels, and Sky preview occupies the second page. The glass
pager, horizontal scrolling, and gallery-focused arrow keys switch pages.
Map gestures remain available for panning. The gallery follows the active page
height, and inactive content is inert for keyboard navigation.
Sky preview loads CDS imagery only when selected. It uses the existing visualization
payload's confirmed ICRS centers and recorded half-power radii, never a new beam
calculation. Rows without confirmed positions are counted as unplottable; known
centers without radii have markers only. The view uses the same current batch,
filters and selected comparison as the offset/frequency charts. Coincident
centers offer a comparison chooser. Fit visible includes the target and plotted
boundaries. Sky context starts at a minimum width of 4.69 arcmin, matching the reference
finder chart; larger selected footprints expand this view. This is the initial
view. Focus selected remains the closer geometry inspection. Fit footprints fits all visible boundaries; Focus
selected fits the target and selected candidate boundary. Overview circles can
be smaller than a pixel; use either fit action to inspect their geometry.
These display scales never change radii or assessment. Selected boundaries use
a thin 1.5 px red line; center separation uses a thin line.


DSS2 resolution can be coarse at ALMA beam scales. Apparent pixelation does not
alter the overlaid coordinates. Circles are evidence illustrations, not new
spatial or full duplication verdicts. Existing SVG export remains the offset
and frequency charts; it does not export external imagery.

The selected candidate has a red boundary and circle center marker; the proposed target
has a cyan cross and label. The position explanation works independently of
external imagery loading. A line joins the centers without exaggerating their
separation. Nearly coincident labels/markers may overlap at the current scale;
the explanation gives the saved numerical separation and radius. This is only
a point-to-boundary relationship, never a proposed footprint or duplication
verdict. Missing evidence is explicitly stated. Other candidates are off by
default; identical source/center/radius boundaries are drawn together when
shown, without removing any records from the comparison list. The optional
one-third reference circle has been removed. Reference imagery can be hidden
for a geometry-only sky view; changing surveys re-enables imagery.

## Imagery comparison

Report imagery presets switch between DSS color and Pan-STARRS DR1 color
(z / mean z,g / g) without changing coordinates, zoom or report evidence.
DSS remains the default all-sky context. Pan-STARRS is partial coverage; a blank
region is not a non-detection. The native layer menu shows the active survey.
CDS properties declare order 9 for DSS color and order 11 for Pan-STARRS color,
both with 512-pixel tiles. These are sampling levels, not angular resolving power.
On the PKS1830 demo, browser resource inspection observed DSS Norder9 and
Pan-STARRS Norder11 tile requests, and the latter visibly improved the close view.
This is not a general guarantee that every requested tile succeeded or that all
regions are covered.

Metadata: https://alasky.cds.unistra.fr/DSS/DSSColor/properties and
https://alasky.cds.unistra.fr/Pan-STARRS/DR1/color-z-zg-g/properties

## Compact inspection layout

Desktop sky inspection places a compact 390 px-high image beside the saved
position explanation and parameters. Below 900 px it stacks vertically. Initial
focus uses wider padding so the boundary occupies roughly a quarter of the
image height; explicit Focus selected retains the closer view. Fullscreen
remains available through Aladin.

Image display exposes the active layer name and neutral-by-default brightness
and contrast sliders (-0.5 to 0.5), using Aladin's image-layer rendering methods.
Reset display returns both to zero. A changed survey resets these adjustments;
the native layer menu is observed as well as the preset buttons. Adjustments
never affect graphical overlays or saved evidence and do not add resolution.

## Controlled reference check

A separate diagnostic page compared DSS color at 4.69 arcmin width and
620 × 310 CSS pixels for the supplied NGC 38 source-panel coordinates
(00:11:46.9892, −05:35:10.800) and the PKS1830 report region. The reference
field reproduced the illustrated bright central object, diffuse surroundings
and upper-right bright star. The PKS field remained crowded and warm-colored
under the same settings. This supports a field/imagery difference rather than
a general inability of the viewer to render the reference. No report
coordinates were altered. Initial context now avoids forcing beam-scale zoom.

## Selection and imagery feedback

Coincident candidates retain all filtered comparison identities on the selected
marker, even while other candidates are hidden. The selected position's chooser
is also available below the map for keyboard use; switching an item preserves
focus and the pressed state. The target marker opens the same chooser when the
positions coincide. Candidate center labels are omitted to avoid colliding with
the target label; marker geometry remains unchanged.

The interpretation card separates the boundary relationship, center separation,
and separation/radius percentage. Missing evidence is explicitly unavailable.
The active survey name stays visible above the map, with pressed preset buttons.
Survey changes report loading and layer initialization failures; successful layer
initialization does not establish tile coverage. Coverage therefore remains
unverified, with a DSS fallback and a geometry-only option for blank fields.
