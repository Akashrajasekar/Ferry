export interface PortFile {
  sha: string;
  branch: string;
  status?: string;
  attempts?: number;
  adaptations?: string[];
  blocker?: string | null;
}
