export interface MetricsFile {
  manual_baseline_minutes?: number | null;
  ferry_run_minutes?: number | null;
  bobcoins_by_task?: Record<string, number>;
  notes?: string;
}
