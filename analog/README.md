Stage D (ML-assisted analog transistor sizing) is out of scope for this
repo, not just postponed: it's a real, separate research direction (a model
proposing/judging transistor sizes or a layout), and building it here would
overpromise. See the full "ML / optimization decision" in
`docs/00-spec.md`.

That decision is about ML *designing or judging a circuit*, specifically.
The applied optimization this project actually does on signal/measurement
data (fitting the CTLE sweep and solving for its optimum) lives in
`src/serdeslink/analysis/optimize.py`, not here.
