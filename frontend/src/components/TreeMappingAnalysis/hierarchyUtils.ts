/** Build a readable hierarchy path from row data */
export function getHierarchyPath(row: {
  block_name?: string;
  compartment?: string;
  sub_compartment?: string;
}): string {
  const parts: string[] = [];
  if (row.block_name && row.block_name !== '-') parts.push(row.block_name);
  if (row.compartment && row.compartment !== '-' && row.compartment !== row.block_name) parts.push(row.compartment);
  if (row.sub_compartment && row.sub_compartment !== '-' && row.sub_compartment !== row.compartment) parts.push(row.sub_compartment);
  return parts.join(' > ') || '-';
}

/** Truncate label for chart axis */
export function truncateLabel(label: string, max = 28): string {
  return label.length > max ? label.substring(0, max - 3) + '...' : label;
}
