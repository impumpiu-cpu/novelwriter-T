import type { BootstrapJobResponse, BootstrapStatus } from '@/types/api'

export const RUNNING_BOOTSTRAP_STATUSES: readonly BootstrapStatus[] = [
  'pending',
  'tokenizing',
  'extracting',
  'windowing',
  'refining',
]

export function isBootstrapStatusRunning(status: BootstrapStatus | null | undefined): boolean {
  return status != null && RUNNING_BOOTSTRAP_STATUSES.includes(status)
}

export function isBootstrapInitialized(job: BootstrapJobResponse | null | undefined): boolean {
  return job?.initialized === true
}
