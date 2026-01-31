"""
Script to add administrative location rows to CalculationDetail.tsx
Adds editable rows for province, district, municipality, ward, and watershed
"""

# Read the file
with open('frontend/src/pages/CalculationDetail.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

# ===== PART 1: Add location rows to Whole Forest table =====
# Find the Soil Texture section in the whole forest table (around line 627-633)
whole_soil_marker = '''                  {/* Soil Texture */}
                  {calculation.result_data?.soil_texture && (
                    <tr className="hover:bg-gray-50">
                      <td className="px-4 py-3 text-sm font-medium text-gray-900">Soil Texture</td>
                      <td className="px-4 py-3 text-sm text-gray-900 capitalize">
                        <EditableCell value={calculation.result_data.soil_texture} onSave={(v) => handleSaveWholeForest('soil_texture', v)} />
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-600">
                        {calculation.result_data?.soil_properties &&
                          Object.entries(calculation.result_data?.soil_properties)
                            .map(([prop, val]: [string, any]) => `${prop}: ${val}`)
                            .join(', ')
                        }
                      </td>
                    </tr>
                  )}'''

whole_soil_pos = content.find(whole_soil_marker)

if whole_soil_pos == -1:
    print("ERROR: Could not find Soil Texture in whole forest table")
    exit(1)

# Insert location rows after soil section
whole_location_rows = '''

                  {/* Administrative Location */}
                  <tr className="bg-gray-100">
                    <td colSpan={3} className="px-4 py-3 text-sm font-semibold text-gray-900">
                      Administrative Location
                    </td>
                  </tr>

                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Province</td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      <EditableCell value={calculation.result_data?.whole_province} onSave={(v) => handleSaveWholeForest('whole_province', v)} />
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600"></td>
                  </tr>

                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">District</td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      <EditableCell value={calculation.result_data?.whole_district} onSave={(v) => handleSaveWholeForest('whole_district', v)} />
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600"></td>
                  </tr>

                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Municipality</td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      <EditableCell value={calculation.result_data?.whole_municipality} onSave={(v) => handleSaveWholeForest('whole_municipality', v)} />
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600"></td>
                  </tr>

                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Ward</td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      <EditableCell value={calculation.result_data?.whole_ward} onSave={(v) => handleSaveWholeForest('whole_ward', v)} />
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600"></td>
                  </tr>

                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Watershed</td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      <EditableCell value={calculation.result_data?.whole_watershed} onSave={(v) => handleSaveWholeForest('whole_watershed', v)} />
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600"></td>
                  </tr>

                  <tr className="hover:bg-gray-50">
                    <td className="px-4 py-3 text-sm font-medium text-gray-900">Major River Basin</td>
                    <td className="px-4 py-3 text-sm text-gray-900">
                      <EditableCell value={calculation.result_data?.whole_major_river_basin} onSave={(v) => handleSaveWholeForest('whole_major_river_basin', v)} />
                    </td>
                    <td className="px-4 py-3 text-sm text-gray-600"></td>
                  </tr>'''

# Find the end of the soil section
soil_end_pos = whole_soil_pos + len(whole_soil_marker)
content = content[:soil_end_pos] + whole_location_rows + content[soil_end_pos:]
print("SUCCESS: Added whole forest administrative location rows")

# ===== PART 2: Add location rows to Block tables =====
# Find the Soil Texture section in block table (around line 940-946)
block_soil_marker = '''                        {/* Soil Texture */}
                        {block.soil_texture && (
                          <tr className="hover:bg-gray-50">
                            <td className="px-4 py-3 text-sm font-medium text-gray-900">Soil Texture</td>
                            <td className="px-4 py-3 text-sm text-gray-900 capitalize">
                              <EditableCell value={block.soil_texture} onSave={(v) => handleSaveBlock(index, 'soil_texture', v)} />
                            </td>
                            <td className="px-4 py-3 text-sm text-gray-600">
                              {block.soil_properties &&
                                Object.entries(block.soil_properties)
                                  .map(([prop, val]: [string, any]) => `${prop}: ${val}`)
                                  .join(', ')
                              }
                            </td>
                          </tr>
                        )}'''

block_soil_pos = content.find(block_soil_marker)

if block_soil_pos == -1:
    print("ERROR: Could not find Soil Texture in block table")
    exit(1)

# Insert location rows after soil section
block_location_rows = '''

                        {/* Administrative Location */}
                        <tr className="bg-gray-100">
                          <td colSpan={3} className="px-4 py-3 text-sm font-semibold text-gray-900">
                            Administrative Location
                          </td>
                        </tr>

                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">Province</td>
                          <td className="px-4 py-3 text-sm text-gray-900">
                            <EditableCell value={block.province} onSave={(v) => handleSaveBlock(index, 'province', v)} />
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-600"></td>
                        </tr>

                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">District</td>
                          <td className="px-4 py-3 text-sm text-gray-900">
                            <EditableCell value={block.district} onSave={(v) => handleSaveBlock(index, 'district', v)} />
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-600"></td>
                        </tr>

                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">Municipality</td>
                          <td className="px-4 py-3 text-sm text-gray-900">
                            <EditableCell value={block.municipality} onSave={(v) => handleSaveBlock(index, 'municipality', v)} />
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-600"></td>
                        </tr>

                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">Ward</td>
                          <td className="px-4 py-3 text-sm text-gray-900">
                            <EditableCell value={block.ward} onSave={(v) => handleSaveBlock(index, 'ward', v)} />
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-600"></td>
                        </tr>

                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">Watershed</td>
                          <td className="px-4 py-3 text-sm text-gray-900">
                            <EditableCell value={block.watershed} onSave={(v) => handleSaveBlock(index, 'watershed', v)} />
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-600"></td>
                        </tr>

                        <tr className="hover:bg-gray-50">
                          <td className="px-4 py-3 text-sm font-medium text-gray-900">Major River Basin</td>
                          <td className="px-4 py-3 text-sm text-gray-900">
                            <EditableCell value={block.major_river_basin} onSave={(v) => handleSaveBlock(index, 'major_river_basin', v)} />
                          </td>
                          <td className="px-4 py-3 text-sm text-gray-600"></td>
                        </tr>'''

# Find the end of the block soil section
block_soil_end_pos = block_soil_pos + len(block_soil_marker)
content = content[:block_soil_end_pos] + block_location_rows + content[block_soil_end_pos:]
print("SUCCESS: Added block-level administrative location rows")

# Write updated content
with open('frontend/src/pages/CalculationDetail.tsx', 'w', encoding='utf-8') as f:
    f.write(content)

print("\nSUCCESS: Administrative location UI added!")
print("\nAdded sections:")
print("  - Whole Forest: Province, District, Municipality, Ward, Watershed, Major River Basin (6 rows)")
print("  - Each Block: Province, District, Municipality, Ward, Watershed, Major River Basin (6 rows per block)")
print("  - All fields are editable with EditableCell component")
print("  - Section headers added with gray background")
