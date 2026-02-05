"""
Add UI for geology, access, and nearby features to CalculationDetail.tsx
"""

# Read the file
with open('frontend/src/pages/CalculationDetail.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# ========================================
# PART 1: Add handler for geology percentages (similar to slope/aspect percentages)
# ========================================

# The handlers already exist (handleSaveWholePercentages and handleSaveBlockPercentages)
# We'll use them for geology too

# ========================================
# PART 2: Add UI rows for WHOLE FOREST
# ========================================

# Find the Major River Basin row (last location row)
whole_river_basin_marker = '''                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Major River Basin</td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      <EditableCell value={calculation.result_data?.whole_major_river_basin} onSave={(v) => handleSaveWholeForest('whole_major_river_basin', v)} />
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600"></td>
                  </tr>'''

whole_river_pos = content.find(whole_river_basin_marker)

if whole_river_pos == -1:
    print("ERROR: Could not find Major River Basin in whole forest table")
    exit(1)

# Add geology, access, and features after Major River Basin
whole_new_rows = '''

                  {/* Geology */}
                  {calculation.result_data?.whole_geology_percentages && Object.keys(calculation.result_data.whole_geology_percentages).length > 0 && (
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">Geology</td>
                      <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                        {Object.entries(calculation.result_data.whole_geology_percentages).map(([cls, pct]: [string, any], idx: number) => (
                          <span key={cls}>
                            {cls}: <EditableCell value={pct} displayValue={pct.toFixed(1) + "%"} onSave={(v) => handleSaveWholePercentages('whole_geology_percentages', cls, v)} className="inline" />
                            {idx < Object.keys(calculation.result_data.whole_geology_percentages).length - 1 && ', '}
                          </span>
                        ))}
                      </td>
                    </tr>
                  )}

                  {/* Access */}
                  {calculation.result_data?.whole_access_info && (
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">Access</td>
                      <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                        <EditableCell value={calculation.result_data.whole_access_info} onSave={(v) => handleSaveWholeForest('whole_access_info', v)} />
                      </td>
                    </tr>
                  )}

                  {/* Nearby Features */}
                  <tr className="bg-gray-100">
                    <td colSpan={3} className="px-4 py-3 text-sm font-semibold text-gray-900">
                      Natural Features (within 100m)
                    </td>
                  </tr>

                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Features North</td>
                    <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                      <EditableCell value={calculation.result_data?.whole_features_north || ''} onSave={(v) => handleSaveWholeForest('whole_features_north', v)} />
                    </td>
                  </tr>

                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Features East</td>
                    <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                      <EditableCell value={calculation.result_data?.whole_features_east || ''} onSave={(v) => handleSaveWholeForest('whole_features_east', v)} />
                    </td>
                  </tr>

                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Features South</td>
                    <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                      <EditableCell value={calculation.result_data?.whole_features_south || ''} onSave={(v) => handleSaveWholeForest('whole_features_south', v)} />
                    </td>
                  </tr>

                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Features West</td>
                    <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                      <EditableCell value={calculation.result_data?.whole_features_west || ''} onSave={(v) => handleSaveWholeForest('whole_features_west', v)} />
                    </td>
                  </tr>'''

insert_after_whole = whole_river_pos + len(whole_river_basin_marker)
content = content[:insert_after_whole] + whole_new_rows + content[insert_after_whole:]
print("SUCCESS: Added geology, access, and features rows to whole forest table")

# ========================================
# PART 3: Add UI rows for BLOCKS
# ========================================

# Find the Major River Basin row in blocks (last location row)
block_river_basin_marker = '''                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">Major River Basin</td>
                          <td className="px-4 py-3 text-sm text-gray-900">
                            <EditableCell value={block.major_river_basin} onSave={(v) => handleSaveBlock(index, 'major_river_basin', v)} />
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-600"></td>
                        </tr>'''

block_river_pos = content.find(block_river_basin_marker)

if block_river_pos == -1:
    print("ERROR: Could not find Major River Basin in block table")
    exit(1)

# Add geology, access, and features after Major River Basin
block_new_rows = '''

                        {/* Geology */}
                        {block.geology_percentages && Object.keys(block.geology_percentages).length > 0 && (
                          <tr className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">Geology</td>
                            <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                              {Object.entries(block.geology_percentages).map(([cls, pct]: [string, any], idx: number) => (
                                <span key={cls}>
                                  {cls}: <EditableCell value={pct} displayValue={pct.toFixed(1) + "%"} onSave={(v) => handleSaveBlockPercentages(index, 'geology_percentages', cls, v)} className="inline" />
                                  {idx < Object.keys(block.geology_percentages).length - 1 && ', '}
                                </span>
                              ))}
                            </td>
                          </tr>
                        )}

                        {/* Access */}
                        {block.access_info && (
                          <tr className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">Access</td>
                            <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                              <EditableCell value={block.access_info} onSave={(v) => handleSaveBlock(index, 'access_info', v)} />
                            </td>
                          </tr>
                        )}

                        {/* Nearby Features */}
                        <tr className="bg-gray-100">
                          <td colSpan={3} className="px-4 py-3 text-sm font-semibold text-gray-900">
                            Natural Features (within 100m)
                          </td>
                        </tr>

                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">Features North</td>
                          <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                            <EditableCell value={block.features_north || ''} onSave={(v) => handleSaveBlock(index, 'features_north', v)} />
                          </td>
                        </tr>

                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">Features East</td>
                          <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                            <EditableCell value={block.features_east || ''} onSave={(v) => handleSaveBlock(index, 'features_east', v)} />
                          </td>
                        </tr>

                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">Features South</td>
                          <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                            <EditableCell value={block.features_south || ''} onSave={(v) => handleSaveBlock(index, 'features_south', v)} />
                          </td>
                        </tr>

                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">Features West</td>
                          <td className="px-4 py-3 text-sm text-gray-900" colSpan={2}>
                            <EditableCell value={block.features_west || ''} onSave={(v) => handleSaveBlock(index, 'features_west', v)} />
                          </td>
                        </tr>'''

insert_after_block = block_river_pos + len(block_river_basin_marker)
content = content[:insert_after_block] + block_new_rows + content[insert_after_block:]
print("SUCCESS: Added geology, access, and features rows to block tables")

# Write updated content
with open('frontend/src/pages/CalculationDetail.tsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("\n" + "="*60)
print("UI IMPLEMENTATION COMPLETE!")
print("="*60)
print("\nAdded to frontend:")
print("  - Geology row (percentage distribution, inline editable)")
print("  - Access row (distance/direction to headquarters, editable)")
print("  - 4 feature rows (N/E/S/W, editable, handles NULL values)")
print("\nAdded to both:")
print("  - Whole Forest table")
print("  - Each Block table")
print("\nTotal new rows:")
print("  - Whole Forest: 7 rows (1 geology + 1 access + 1 header + 4 features)")
print("  - Each Block: 7 rows (same structure)")
