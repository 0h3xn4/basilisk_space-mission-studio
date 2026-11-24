# Syncing with upstream Basilisk

This repository is a fork of [AVSLab/basilisk](https://github.com/AVSLab/basilisk).
This page covers how to take new upstream commits, how to move the tool
to a new Basilisk release, and how to refresh the upstream part of the
root `README.md`.

## Two different things

- **The Basilisk sources in this repository** (`src/`, `docs/`,
  `examples/`, ...) are upstream's. The tool does not build or import
  them.
- **The Basilisk the tool runs** is the `bsk` wheel from PyPI, pinned to
  the verified version (`QUALIFIED_BASILISK_VERSION` in
  `spacemissionstudio/dependencies.py`, currently 2.12.0).

So merging upstream commits changes nothing the tool runs. Moving the
tool to a new Basilisk is a separate, deliberate step.

## Take new upstream commits

```bash
git remote add upstream https://github.com/AVSLab/basilisk.git   # once
git fetch upstream develop
git switch develop
git switch -c sync-upstream
git merge upstream/develop
```

Conflicts can only appear in the few files the fork changed outside
`SpaceMissionStudio/`: `README.md`, `.gitignore` and
`.github/workflows/`. Resolve them, then open a pull request.

## Refresh the upstream README

The root `README.md` has the tool's part at the top and upstream's
README below it, between these two markers:

```
<!-- BEGIN UPSTREAM README -->
...
<!-- END UPSTREAM README -->
```

An untouched copy of the same upstream text is kept in
`docs/upstream/README.upstream.md` (in the repository root's `docs/`
folder). To see whether upstream changed its README since the last sync:

```bash
git fetch upstream develop
git show upstream/develop:README.md > /tmp/README.upstream.new
diff -u docs/upstream/README.upstream.md /tmp/README.upstream.new
```

If it did:

1. Copy the new text over the copy, unchanged:
   `cp /tmp/README.upstream.new docs/upstream/README.upstream.md`.
   The copy stays byte-for-byte upstream's; it has no header of its own.
2. Replace everything between the two markers in `README.md` with the
   same text, every heading one level lower (outside code blocks):

   ```bash
   python3 - <<'PY'
   up = open("docs/upstream/README.upstream.md").read().split("\n")
   out, fence = [], False
   for line in up:
       if line.startswith("```"):
           fence = not fence
       out.append("#" + line if (not fence and line.startswith("#")) else line)
   readme = open("README.md").read()
   begin, end = "<!-- BEGIN UPSTREAM README -->\n", "<!-- END UPSTREAM README -->"
   head, rest = readme.split(begin)
   _, tail = rest.split(end)
   open("README.md", "w").write(head + begin + "\n".join(out).rstrip("\n") + "\n" + end + tail)
   PY
   ```

   Change nothing else. Relative links still work, because the README
   stays at the repository root where upstream has it. One upstream link,
   `docs/source/examples/index.rst`, points at a page Sphinx generates;
   it is broken on GitHub upstream too, and stays as it is.
3. Update the commit named under "Original Basilisk README" in
   `README.md`.
4. Note what changed in `SpaceMissionStudio/docs/DOCS_AUDIT.md` section 5.

## Move the tool to a new Basilisk release

This is a requalification, described in
[`compliance/docs/SMP.md`](../../compliance/docs/SMP.md) section 8
("Requalify a new Basilisk release"):

1. Install the new release in a fresh environment:
   `pip install "bsk[all]==X.Y.Z"`.
2. Run the full suite and the validation cases against it.
3. Only then change `QUALIFIED_BASILISK_VERSION`, the installers'
   `bsk[all]==` pin (`BASILISK_REQUIREMENT` in
   `packaging/bundle_python.py`), `bsk==` in `packaging/constraints.txt`
   (then `python packaging/hash_constraints.py` to rewrite
   `constraints-hashes.txt`, which also names any new dependency left
   unpinned), and the `bsk[all]==` commands
   in the documentation (`grep -rn "bsk\[all\]==" --include=*.md .`).
4. Re-vendor the flight-software sources the export uses
   (`spacemissionstudio/fsw_export/basilisk_fsw_sources.*`, from the new
   release's sources): set `BASILISK_VERSION` and `BASILISK_REVISION` (the
   release tag's commit) in `spacemissionstudio/fsw_export/catalog.py`,
   run `python scripts/vendor_basilisk_fsw.py --repo <a Basilisk clone
   with that tag>` from `SpaceMissionStudio/`, and run
   `tests/test_fsw_vendored_sources.py`.
5. Check the points of Basilisk's Monte Carlo framework that the batch
   relies on (risk R1 of `docs/developer/monte-carlo-plan.md`):
   `RetentionPolicy.addRetentionFunction` and the `custom` data it puts
   in each `run<N>.data` (the outcomes), the data writer's file per
   custom key (`spacemissionstudio_outcome*.data`, in
   `monte_carlo_results.BATCH_FILE_PATTERNS`), the order of the entries
   in `run<N>.json`, and `SimulationExecutor.applyModification`, which
   applies them when a case runs again (`engine.monte_carlo.prepare_case`;
   the RNG seeds are entries too). `tests/test_monte_carlo.py` fails if
   one of them changes; `test_a_case_run_again_is_the_batchs_case`
   compares a case run again with the batch to 1e-6 m. The batch seed
   (decision MC-20) relies on the order of `SimulationExecutor.__call__`:
   `np.random.seed(index * 10)` and `random.seed(index * 10)`, then the
   creation function, then the RNG seeds (`random`) and the dispersions
   (NumPy); `engine.monte_carlo.basilisk_run_index` reads the index back
   from NumPy's freshly seeded state.
   `test_without_a_seed_the_creation_function_leaves_basilisks_seeding_alone`
   and `test_a_batch_seed_gives_other_draws_and_the_same_draws_again` fail
   if that changes. The density scale (decision MC-37) relies on three
   more points: the atmosphere models write `AtmoPropsMsg`
   (`neutralDensity`, `localTemp`) and the sphere and facet drag read it
   through `atmoDensInMsg`, so `engine.density_scale` can sit between
   them; no model has its own density scale (if a new Basilisk adds one
   to `AtmosphereBase`, use it and drop the module); and
   `UniformDispersion.generate` draws `random.uniform(lo, hi)` once and
   divides by the half-width (`engine.monte_carlo._UniformDensityScale`
   repeats that draw for equal bounds).
   `test_the_density_that_drag_reads_is_the_models_times_the_scale` and
   `test_a_uniform_density_scale_with_equal_bounds_gives_that_scale` fail
   if they change.

---

**Next:** [Releasing](releasing.md) · [Developer guide](README.md)
