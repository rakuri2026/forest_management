"""
Test Species Matcher Service
Demonstrates species identification from various input formats
"""

import sys
import io

# Set UTF-8 encoding for console output (Windows compatibility)
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.path.append('backend')

from app.services.species_matcher import SpeciesMatcher


def test_species_matcher():
    """Test species matcher with various inputs"""

    print("=" * 70)
    print("Species Matcher Test")
    print("=" * 70)
    print()

    # Initialize matcher
    matcher = SpeciesMatcher()

    print(f"Loaded {len(matcher.species_data)} species")
    print()

    # Test cases
    test_inputs = [
        # Numeric codes
        "1",
        "18",
        "5",

        # Scientific names
        "Shorea robusta",
        "Alnus nepalensis",
        "Dalbergia sissoo",

        # Abbreviated codes (NEW!)
        "sho",          # Should match Shorea robusta
        "Sho",          # Case insensitive
        "rob",          # Should match Shorea robusta (epithet)
        "sho rob",      # Should match Shorea robusta (both parts)
        "sho/rob",      # With slash separator
        "sho-rob",      # With dash separator
        "aln",          # Should match Alnus nepalensis
        "aln nep",      # Should match Alnus nepalensis
        "dal",          # Should match Dalbergia sissoo
        "dal sis",      # Should match Dalbergia sissoo
        "pin",          # Should match Pinus (multiple species)
        "pin rox",      # Should match Pinus roxburghii
        "que",          # Should match Quercus spp
        "sch",          # Should match Schima wallichii

        # Nepali Unicode
        "साल",
        "उत्तिस",
        "खयर",

        # Nepali Romanized
        "Sal",
        "Uttis",
        "Khayar",

        # Common names
        "Khair",
        "Utis",
        "Sisau",

        # Typos / Variations
        "Shisham",  # Should match Dalbergia sissoo
        "Sissoo",   # Alternative spelling
        "Chir Pine",  # Should match Pinus roxburghii

        # Invalid
        "XYZ123",
        "999",
        "ab",       # Too short
    ]

    print("Testing Species Identification:")
    print("-" * 70)

    for input_text in test_inputs:
        result = matcher.identify(input_text)

        if result:
            species = result["species"]
            print(f"Input: '{input_text}'")
            print(f"  => Matched: {species['species']} ({species['name_nep']})")
            print(f"  => Code: {species['code']}")
            print(f"  => Match Type: {result['match_type']}")
            print(f"  => Confidence: {result['confidence']}")
            print(f"  => Field: {result['matched_field']}")
        else:
            print(f"Input: '{input_text}'")
            print(f"  => No match found")

        print()

    # Test batch identification
    print("=" * 70)
    print("Batch Identification Test")
    print("=" * 70)
    print()

    batch_inputs = ["1", "साल", "Uttis", "18", "Khair"]
    results = matcher.identify_batch(batch_inputs)

    for inp, result in zip(batch_inputs, results):
        if result:
            print(f"{inp:15} => {result['species']['species']:30} (confidence: {result['confidence']})")
        else:
            print(f"{inp:15} => Not found")

    print()

    # Test suggestions (autocomplete)
    print("=" * 70)
    print("Autocomplete Suggestions Test")
    print("=" * 70)
    print()

    partial_inputs = ["Sal", "Pin", "Ac", "उत्", "Si"]

    for partial in partial_inputs:
        suggestions = matcher.suggest(partial, limit=3)
        print(f"Input: '{partial}'")
        for i, sug in enumerate(suggestions, 1):
            species = sug["species"]
            print(f"  {i}. {species['species']} ({species['name_nep']}) - confidence: {sug['confidence']}")
        print()

    # Test validation
    print("=" * 70)
    print("Column Validation Test (CSV Upload Scenario)")
    print("=" * 70)
    print()

    # Simulate a column of species data from user upload
    species_column = [
        "1",           # Valid code
        "साल",         # Valid Nepali
        "Uttis",       # Valid romanized
        "Shisham",     # Typo/variation
        "XYZ",         # Invalid
        "",            # Empty
        "18",          # Valid code
        "Pine",        # Partial match
    ]

    validation_result = matcher.validate_species_column(species_column, min_confidence=0.6)

    print(f"Total rows: {validation_result['total']}")
    print(f"Matched: {validation_result['matched']}")
    print(f"Unmatched: {validation_result['unmatched']}")
    print(f"Low confidence: {validation_result['low_confidence']}")
    print()

    if validation_result['unmatched_details']:
        print("Unmatched rows:")
        for item in validation_result['unmatched_details']:
            print(f"  Row {item['row']}: '{item['input']}' - {item['reason']}")
            if item.get('suggestions'):
                print(f"    Suggestions:")
                for sug in item['suggestions'][:2]:
                    print(f"      - {sug['species']['species']} (confidence: {sug['confidence']})")
        print()

    if validation_result['low_confidence_details']:
        print("Low confidence matches (need user confirmation):")
        for item in validation_result['low_confidence_details']:
            print(f"  Row {item['row']}: '{item['input']}'")
            print(f"    → Suggested: {item['suggested_species']['species']} (confidence: {item['confidence']})")
        print()


if __name__ == "__main__":
    test_species_matcher()
