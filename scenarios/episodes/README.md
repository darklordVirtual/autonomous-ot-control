# Episode revision history

The `*-v1.json` episodes are retained unchanged as historical inputs for the October results (REMORA `123a5fd0`). The active `*-v2.json` episodes retain the same proposal streams and oracle verdicts, but bind the new immutable REMORA pin `06e7a02b` and upstream-lock digest. They are new test inputs, not new measured results. The `runner.episode check` command must pass for each active episode; rerun the A/B/C experiment before reporting new-pin outcomes.
