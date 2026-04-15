# GazeVibe Experiment Data Analysis Script

Based on the experiment design specification, implements 6 validation dimensions for automated analysis.

## Usage

```bash
# One-click run (using uv for dependency management)
./scripts/run.sh
```

## Output

The script outputs analysis results to the terminal and generates vector charts (SVG) in `docs/figures/`:

- `dimension1_eye_effectiveness.svg` - Eye tracking metrics effectiveness
- `dimension2_normalization.svg` - Normalization algorithm effectiveness
- `dimension4_ema_convergence.svg` - EMA convergence analysis
- `dimension6_mode_comparison.svg` - Mode comparison analysis

All charts are in English.

## Analysis Dimensions

### Dimension 1: Eye Tracking Metrics Effectiveness

- Time allocation metrics (choice-time consistency rate)
- Saccade pattern metrics (saccadeCount vs decisionLatency)
- Cognitive load metrics (correlation analysis)
- Decision prediction metrics (gazeBias predicts finalChoice)

### Dimension 2: Normalization Algorithm Effectiveness

- Length difference case analysis
- Original gazeBias vs normalized comparison
- Consistency rate improvement after normalization

### Dimension 3: Adjustment Score Prediction Ability

- Single indicator prediction ability (point-biserial correlation)
- Adjustment score descriptive statistics

### Dimension 4: EMA Convergence Analysis

- Convergence speed analysis
- Post-convergence fluctuation range

### Dimension 6: Mode Comparison Analysis

- Behavioral metrics comparison (decision time, choice ratio)
- Eye metrics comparison (full vs manual)
- Statistical significance testing

## Dependencies

Dependencies are automatically managed by uv:
- pandas
- numpy
- matplotlib
- seaborn
- scipy
