"""
Diameter Classification Utility

Classifies trees by diameter (DBH) into two systems:
1. Simplified 3-category: Regeneration, Pole, Tree
2. Detailed 7-category: Regeneration, Small pole, Large pole, Small tree, etc.

Author: Forest Management System
Date: February 13, 2026
"""

from typing import Optional, Tuple, Dict, Any
import pandas as pd


class DiameterClassifier:
    """Classifies trees by diameter using two classification systems"""

    def __init__(self):
        """Initialize the diameter classifier"""
        pass

    @staticmethod
    def classify_simple(dbh: float) -> Optional[str]:
        """
        Classify tree using simplified 3-category system

        Args:
            dbh: Diameter at breast height in cm

        Returns:
            - 'Regeneration' for 1-10 cm
            - 'Pole' for 10-30 cm
            - 'Tree' for >30 cm
            - None for invalid/null values
        """
        if pd.isna(dbh):
            return None

        try:
            dbh_value = float(dbh)
        except (ValueError, TypeError):
            return None

        if dbh_value < 1:
            return None
        elif 1 <= dbh_value < 10:
            return "Regeneration"
        elif 10 <= dbh_value < 30:
            return "Pole"
        elif dbh_value >= 30:
            return "Tree"
        else:
            return None

    @staticmethod
    def classify_detailed(dbh: float) -> Optional[str]:
        """
        Classify tree using detailed 7-category system

        Args:
            dbh: Diameter at breast height in cm

        Returns:
            Detailed category with range, e.g., 'Small pole (10-20)'
            None for invalid/null values
        """
        if pd.isna(dbh):
            return None

        try:
            dbh_value = float(dbh)
        except (ValueError, TypeError):
            return None

        if dbh_value < 1:
            return None
        elif 1 <= dbh_value < 10:
            return "Regeneration"
        elif 10 <= dbh_value < 20:
            return "Small pole (10-20)"
        elif 20 <= dbh_value < 30:
            return "Large pole (20-30)"
        elif 30 <= dbh_value < 40:
            return "Small tree (30-40)"
        elif 40 <= dbh_value < 50:
            return "Medium tree (40-50)"
        elif 50 <= dbh_value < 60:
            return "Large tree (50-60)"
        elif dbh_value >= 60:
            return "Very large tree (>60)"
        else:
            return None

    @staticmethod
    def classify_dataframe(df: pd.DataFrame, dia_column: str) -> Tuple[pd.DataFrame, Dict[str, Any]]:
        """
        Add classification columns to a DataFrame

        Args:
            df: DataFrame to classify
            dia_column: Name of the diameter column

        Returns:
            Tuple of (classified_df, report)
            - classified_df: DataFrame with 'stand_type' and 'dbh_class' columns added
            - report: Dictionary with classification statistics
        """
        if dia_column not in df.columns:
            return df, {
                'status': 'skipped',
                'message': f'Column "{dia_column}" not found in data'
            }

        # Add classification columns
        df['stand_type'] = df[dia_column].apply(DiameterClassifier.classify_simple)
        df['dbh_class'] = df[dia_column].apply(DiameterClassifier.classify_detailed)

        # Generate statistics
        simple_counts = df['stand_type'].value_counts().to_dict()
        detailed_counts = df['dbh_class'].value_counts().to_dict()

        total_classified = df['stand_type'].notna().sum()
        total_rows = len(df)

        # Calculate percentages for simplified classification
        simple_stats = {}
        for category in ['Regeneration', 'Pole', 'Tree']:
            count = simple_counts.get(category, 0)
            percentage = (count / total_classified * 100) if total_classified > 0 else 0
            simple_stats[category] = {
                'count': count,
                'percentage': percentage
            }

        # Calculate percentages for detailed classification
        detailed_stats = {}
        for category in [
            'Regeneration',
            'Small pole (10-20)',
            'Large pole (20-30)',
            'Small tree (30-40)',
            'Medium tree (40-50)',
            'Large tree (50-60)',
            'Very large tree (>60)'
        ]:
            count = detailed_counts.get(category, 0)
            percentage = (count / total_classified * 100) if total_classified > 0 else 0
            detailed_stats[category] = {
                'count': count,
                'percentage': percentage
            }

        report = {
            'status': 'completed',
            'total_rows': total_rows,
            'total_classified': total_classified,
            'simple_distribution': simple_stats,
            'detailed_distribution': detailed_stats
        }

        return df, report

    @staticmethod
    def get_summary(report: Dict[str, Any]) -> str:
        """
        Generate a human-readable summary of diameter classification

        Args:
            report: Report dictionary from classify_dataframe()

        Returns:
            Formatted summary string
        """
        if report['status'] == 'skipped':
            return report['message']

        lines = [
            "DIAMETER CLASSIFICATION SUMMARY:",
            f"Total trees: {report['total_classified']}/{report['total_rows']}",
            "",
            "SIMPLIFIED DISTRIBUTION (Stand Type):"
        ]

        # Simplified distribution
        for category in ['Regeneration', 'Pole', 'Tree']:
            stats = report['simple_distribution'].get(category, {'count': 0, 'percentage': 0})
            lines.append(f"  {category:15} {stats['count']:5} trees ({stats['percentage']:5.1f}%)")

        lines.append("")
        lines.append("DETAILED DISTRIBUTION (DBH Class):")

        # Detailed distribution
        for category in [
            'Regeneration',
            'Small pole (10-20)',
            'Large pole (20-30)',
            'Small tree (30-40)',
            'Medium tree (40-50)',
            'Large tree (50-60)',
            'Very large tree (>60)'
        ]:
            stats = report['detailed_distribution'].get(category, {'count': 0, 'percentage': 0})
            if stats['count'] > 0:  # Only show categories with trees
                lines.append(f"  {category:25} {stats['count']:5} trees ({stats['percentage']:5.1f}%)")

        return '\n'.join(lines)
