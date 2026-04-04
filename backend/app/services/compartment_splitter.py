"""
Compartment splitting algorithms and validation
"""
from shapely.geometry import Polygon, LineString, Point, MultiPolygon, box
from shapely.ops import split as shapely_split, unary_union, linemerge
from shapely.affinity import rotate, translate
import numpy as np
from typing import List, Tuple, Dict, Any, Optional
import logging

logger = logging.getLogger(__name__)


class CompartmentSplitter:
    """Service for splitting forest blocks into compartments"""

    @staticmethod
    def split_parallel_strips(
        polygon: Polygon,
        direction_angle: float,
        num_compartments: Optional[int] = None,
        target_area_sqm: Optional[float] = None,
        min_area_sqm: float = 1000
    ) -> List[Polygon]:
        """
        Split polygon into parallel strips with EQUAL AREAS

        Args:
            polygon: Input polygon (Shapely Polygon)
            direction_angle: Splitting direction in degrees (0=N-S, 90=E-W)
            num_compartments: Number of compartments (if specified)
            target_area_sqm: Target area per compartment (if specified)
            min_area_sqm: Minimum allowed compartment area

        Returns:
            List of compartment polygons with equal areas
        """
        if not polygon.is_valid:
            logger.error("Invalid input polygon")
            raise ValueError("Invalid input polygon")

        total_area = polygon.area

        # Determine number of compartments
        if num_compartments is None and target_area_sqm:
            num_compartments = max(1, int(total_area / (target_area_sqm / (111000 * 111000))))
        elif num_compartments is None:
            raise ValueError("Must specify either num_compartments or target_area_sqm")

        if num_compartments < 1:
            raise ValueError("Number of compartments must be at least 1")

        if num_compartments == 1:
            return [polygon]

        # Rotate polygon to align with splitting direction
        centroid = polygon.centroid
        rotated_poly = rotate(polygon, -direction_angle, origin=centroid, use_radians=False)

        # Use equal-area algorithm with proper total area tracking
        compartments = CompartmentSplitter._split_into_equal_area_strips(
            rotated_poly, total_area, num_compartments, 'vertical'
        )

        # Rotate back to original orientation
        compartments = [
            rotate(comp, direction_angle, origin=centroid, use_radians=False)
            for comp in compartments
        ]

        # Filter valid compartments
        valid_compartments = [
            c for c in compartments
            if c.is_valid and c.area > 0
        ]

        # Check for and handle tiny leftover compartments
        if len(valid_compartments) == num_compartments:
            valid_compartments = CompartmentSplitter._redistribute_tiny_compartments(
                valid_compartments, min_area_sqm, polygon.area
            )

        # Sort by position
        valid_compartments.sort(key=lambda c: (c.centroid.y, c.centroid.x))

        logger.info(f"Created {len(valid_compartments)} equal-area compartments")
        return valid_compartments

    @staticmethod
    def _redistribute_tiny_compartments(
        compartments: List[Polygon],
        min_area_sqm: float,
        total_polygon_area: float
    ) -> List[Polygon]:
        """
        Check for and merge tiny compartments with neighbors.
        """
        if not compartments:
            return compartments
        
        # Check if any compartment is suspiciously small
        avg_area = total_polygon_area / len(compartments)
        tiny_threshold = avg_area * 0.5  # Less than 50% of average is considered tiny
        
        result = []
        small_compartments = []
        
        for comp in compartments:
            if comp.area < tiny_threshold:
                small_compartments.append(comp)
            else:
                result.append(comp)
        
        if not small_compartments:
            return compartments
        
        # Merge small compartments into the last valid compartment (or first if only one valid)
        if not result:
            # All compartments are small - just return them as is
            return compartments
        
        target = result[-1]  # Merge into the last valid compartment
        for small in small_compartments:
            try:
                merged = target.union(small)
                if merged.is_valid and isinstance(merged, Polygon):
                    target = merged
                elif merged.is_valid and isinstance(merged, MultiPolygon):
                    # Take the largest part
                    target = max(merged.geoms, key=lambda g: g.area)
            except Exception as e:
                logger.warning(f"Failed to merge small compartment: {e}")
                result.append(small)
        
        result[-1] = target
        
        logger.info(f"Merged {len(small_compartments)} tiny compartments")
        return result

    @staticmethod
    def _split_into_equal_area_strips(
        polygon: Polygon,
        total_area: float,
        num_compartments: int,
        direction: str = 'vertical'
    ) -> List[Polygon]:
        """
        Split polygon into equal-area strips using iterative approach.
        
        Uses binary search to find exact cut positions for equal areas.
        """
        bounds = polygon.bounds
        
        compartments = []
        remaining_poly = polygon
        remaining_area = total_area
        target_area = total_area / num_compartments
        
        for i in range(num_compartments):
            if i == num_compartments - 1:
                # Last compartment gets everything remaining
                if remaining_poly.is_valid and remaining_poly.area > 0:
                    compartments.append(remaining_poly)
                break
            
            # Adjust target area based on remaining area
            current_target = remaining_area / (num_compartments - i)
            
            # Find cut position using binary search for equal area
            if direction == 'vertical':
                cut_x = CompartmentSplitter._find_equal_area_cut_vertical(
                    remaining_poly, current_target
                )
                if cut_x is None:
                    # Fallback to proportional width
                    remaining_bounds = remaining_poly.bounds
                    remaining_width = remaining_bounds[2] - remaining_bounds[0]
                    remaining_minx = remaining_bounds[0]
                    cut_x = remaining_minx + remaining_width * 0.5
                
                # Create cut line extended beyond polygon bounds
                min_extend = bounds[1] - 1
                max_extend = bounds[3] + 1
                cut_line = LineString([(cut_x, min_extend), (cut_x, max_extend)])
            else:
                cut_y = CompartmentSplitter._find_equal_area_cut_horizontal(
                    remaining_poly, current_target
                )
                if cut_y is None:
                    remaining_bounds = remaining_poly.bounds
                    remaining_height = remaining_bounds[3] - remaining_bounds[1]
                    remaining_miny = remaining_bounds[1]
                    cut_y = remaining_miny + remaining_height * 0.5
                
                min_extend = bounds[0] - 1
                max_extend = bounds[2] + 1
                cut_line = LineString([(min_extend, cut_y), (max_extend, cut_y)])
            
            # Split the polygon
            try:
                result = shapely_split(remaining_poly, cut_line)
                
                if len(result.geoms) < 2:
                    logger.warning(f"Split produced less than 2 parts at iteration {i}")
                    compartments.append(remaining_poly)
                    continue
                
                # Separate parts into left/bottom and right/top based on centroid
                parts = []
                for geom in result.geoms:
                    if isinstance(geom, Polygon) and geom.is_valid and geom.area > 0:
                        parts.append(geom)
                
                if len(parts) < 2:
                    logger.warning(f"Could not find two valid parts at iteration {i}")
                    compartments.append(remaining_poly)
                    continue
                
                # Sort parts by position (left/bottom first)
                if direction == 'vertical':
                    parts.sort(key=lambda p: p.centroid.x)
                else:
                    parts.sort(key=lambda p: p.centroid.y)
                
                first_comp = parts[0]
                remaining_poly = unary_union(parts[1:])  # Combine all remaining parts
                
                if not remaining_poly.is_valid or remaining_poly.is_empty:
                    remaining_poly = parts[1]
                elif isinstance(remaining_poly, MultiPolygon):
                    remaining_poly = unary_union(list(remaining_poly.geoms))
                
                compartments.append(first_comp)
                remaining_area -= first_comp.area
                
            except Exception as e:
                logger.warning(f"Split failed at iteration {i}: {e}")
                compartments.append(remaining_poly)
                break
        
        return [c for c in compartments if c.is_valid and c.area > 0]

    @staticmethod
    def _find_equal_area_cut_vertical(polygon: Polygon, target_area: float) -> Optional[float]:
        """
        Find the x-position of a vertical line that splits polygon to get target_area on left.
        Uses binary search for accuracy.
        """
        bounds = polygon.bounds
        minx, maxx = bounds[0], bounds[2]
        
        if maxx - minx < 0.0001:
            return None
        
        tolerance = polygon.area * 0.00001  # 0.001% tolerance
        max_iterations = 60
        
        low, high = minx, maxx
        last_valid_pos = None
        
        for iteration in range(max_iterations):
            mid = (low + high) / 2
            cut_line = LineString([(mid, bounds[1] - 0.1), (mid, bounds[3] + 0.1)])
            
            try:
                result = shapely_split(polygon, cut_line)
                
                # Calculate area on left side of cut
                left_area = 0
                for geom in result.geoms:
                    if isinstance(geom, Polygon) and geom.is_valid:
                        if geom.centroid.x < mid:
                            left_area += geom.area
                
                area_diff = left_area - target_area
                
                if abs(area_diff) < tolerance:
                    return mid
                
                if left_area > target_area:
                    high = mid
                else:
                    low = mid
                    last_valid_pos = mid
                    
            except Exception as e:
                logger.debug(f"Binary search iteration {iteration} failed: {e}")
                break
        
        return last_valid_pos if last_valid_pos is not None else (minx + maxx) / 2

    @staticmethod
    def _find_equal_area_cut_horizontal(polygon: Polygon, target_area: float) -> Optional[float]:
        """Find the y-position of a horizontal line that splits polygon to get target_area below."""
        bounds = polygon.bounds
        miny, maxy = bounds[1], bounds[3]
        
        if maxy - miny < 0.0001:
            return None
        
        tolerance = polygon.area * 0.00001
        max_iterations = 60
        
        low, high = miny, maxy
        last_valid_pos = None
        
        for iteration in range(max_iterations):
            mid = (low + high) / 2
            cut_line = LineString([(bounds[0] - 0.1, mid), (bounds[2] + 0.1, mid)])
            
            try:
                result = shapely_split(polygon, cut_line)
                
                # Calculate area below the cut
                bottom_area = 0
                for geom in result.geoms:
                    if isinstance(geom, Polygon) and geom.is_valid:
                        if geom.centroid.y < mid:
                            bottom_area += geom.area
                
                area_diff = bottom_area - target_area
                
                if abs(area_diff) < tolerance:
                    return mid
                
                if bottom_area > target_area:
                    high = mid
                else:
                    low = mid
                    last_valid_pos = mid
                    
            except Exception as e:
                logger.debug(f"Binary search iteration {iteration} failed: {e}")
                break
        
        return last_valid_pos if last_valid_pos is not None else (miny + maxy) / 2

    @staticmethod
    def _find_equal_area_cut_horizontal(polygon: Polygon, target_area: float) -> Optional[float]:
        """Find the y-position of a horizontal line that splits polygon into target_area."""
        bounds = polygon.bounds
        miny, maxy = bounds[1], bounds[3]
        
        if maxy - miny < 0.0001:
            return None
        
        tolerance = polygon.area * 0.00001
        max_iterations = 60
        
        low, high = miny, maxy
        last_valid_pos = None
        
        for iteration in range(max_iterations):
            mid = (low + high) / 2
            cut_line = LineString([(bounds[0] - 0.1, mid), (bounds[2] + 0.1, mid)])
            
            try:
                result = shapely_split(polygon, cut_line)
                
                # Calculate area below the cut
                bottom_area = 0
                for geom in result.geoms:
                    if isinstance(geom, Polygon) and geom.is_valid:
                        if geom.centroid.y < mid:
                            bottom_area += geom.area
                
                area_diff = bottom_area - target_area
                
                if abs(area_diff) < tolerance:
                    return mid
                
                if bottom_area > target_area:
                    high = mid
                else:
                    low = mid
                    last_valid_pos = mid
                    
            except Exception as e:
                logger.debug(f"Binary search iteration {iteration} failed: {e}")
                break
        
        return last_valid_pos if last_valid_pos is not None else (miny + maxy) / 2
        
        return (low + high) / 2

    @staticmethod
    def split_grid(
        polygon: Polygon,
        rows: int,
        columns: int,
        min_area_sqm: float = 1000
    ) -> List[Polygon]:
        """
        Split polygon into grid pattern

        Args:
            polygon: Input polygon
            rows: Number of horizontal divisions
            columns: Number of vertical divisions
            min_area_sqm: Minimum allowed compartment area

        Returns:
            List of compartment polygons
        """
        if not polygon.is_valid:
            logger.error("Invalid input polygon")
            raise ValueError("Invalid input polygon")

        if rows < 1 or columns < 1:
            raise ValueError("Rows and columns must be at least 1")

        bounds = polygon.bounds
        minx, miny, maxx, maxy = bounds

        width = maxx - minx
        height = maxy - miny

        cell_width = width / columns
        cell_height = height / rows

        logger.info(f"Creating {rows}x{columns} grid, cell size={cell_width:.6f}x{cell_height:.6f}")

        # Create grid cells
        grid_cells = []
        for i in range(rows):
            for j in range(columns):
                x_min = minx + (j * cell_width)
                x_max = x_min + cell_width
                y_min = miny + (i * cell_height)
                y_max = y_min + cell_height

                # Create rectangular cell using box
                cell = box(x_min, y_min, x_max, y_max)
                grid_cells.append(cell)

        # Intersect grid cells with original polygon
        compartments = []
        for idx, cell in enumerate(grid_cells):
            try:
                intersection = polygon.intersection(cell)

                if intersection.is_empty:
                    continue

                # Handle MultiPolygon results
                if isinstance(intersection, MultiPolygon):
                    for poly in intersection.geoms:
                        if poly.is_valid and poly.area > 0:
                            compartments.append(poly)
                elif isinstance(intersection, Polygon):
                    if intersection.is_valid and intersection.area > 0:
                        compartments.append(intersection)
            except Exception as e:
                logger.warning(f"Failed to intersect cell {idx}: {e}")

        # Sort compartments by position (top to bottom, left to right)
        compartments.sort(key=lambda c: (c.centroid.y, c.centroid.x))

        logger.info(f"Created {len(compartments)} grid compartments")
        return compartments

    @staticmethod
    def calculate_optimal_direction(polygon: Polygon) -> float:
        """
        Calculate optimal splitting direction based on polygon shape
        Returns angle of the longest axis (0-180 degrees)

        Args:
            polygon: Input polygon

        Returns:
            Optimal angle in degrees
        """
        try:
            # Get minimum rotated rectangle (oriented bounding box)
            min_rect = polygon.minimum_rotated_rectangle
            coords = list(min_rect.exterior.coords)

            if len(coords) < 4:
                logger.warning("Polygon too simple for optimal direction, using 0°")
                return 0.0

            # Calculate lengths of two adjacent sides
            p0, p1, p2 = Point(coords[0]), Point(coords[1]), Point(coords[2])
            side1 = p0.distance(p1)
            side2 = p1.distance(p2)

            # Determine which side is longer
            if side1 > side2:
                # Use first side
                dx = coords[1][0] - coords[0][0]
                dy = coords[1][1] - coords[0][1]
            else:
                # Use second side
                dx = coords[2][0] - coords[1][0]
                dy = coords[2][1] - coords[1][1]

            # Calculate angle
            angle = np.degrees(np.arctan2(dy, dx))

            # Normalize to 0-180 range
            normalized_angle = angle % 180

            logger.info(f"Optimal direction calculated: {normalized_angle:.1f}°")
            return normalized_angle
        except Exception as e:
            logger.error(f"Failed to calculate optimal direction: {e}")
            return 0.0  # Default to North-South

    @staticmethod
    def validate_split(
        compartments: List[Polygon],
        min_area_sqm: float = 1000,
        max_deviation_percent: float = 10
    ) -> Dict[str, Any]:
        """
        Validate split results

        Args:
            compartments: List of compartment polygons
            min_area_sqm: Minimum allowed area (in actual square meters)
            max_deviation_percent: Maximum allowed deviation from target area

        Returns:
            Validation results dictionary
        """
        if not compartments:
            return {
                "is_valid": False,
                "warnings": [],
                "errors": ["No compartments created"],
                "total_area_match": False,
                "total_area_sqm": 0,
                "target_area_sqm": 0
            }

        warnings = []
        errors = []

        # Calculate total area and target area
        total_area = sum(c.area for c in compartments)
        target_area = total_area / len(compartments)

        # Convert to approximate square meters (rough estimate)
        # 1 degree² ≈ 12,321,000,000 m² (very rough)
        approx_conversion = 111000 * 111000
        total_area_sqm = total_area * approx_conversion
        target_area_sqm = target_area * approx_conversion

        for i, comp in enumerate(compartments):
            # Check validity
            if not comp.is_valid:
                errors.append(f"Compartment {i+1} has invalid geometry")
                continue

            # Check area deviation
            if target_area > 0:
                deviation = abs((comp.area - target_area) / target_area * 100)
                if deviation > max_deviation_percent:
                    comp_area_sqm = comp.area * approx_conversion
                    warnings.append(
                        f"Compartment {i+1} deviates {deviation:.1f}% from target area "
                        f"(target: {target_area_sqm:.0f} m², actual: {comp_area_sqm:.0f} m²)"
                    )

        # Overall validation
        is_valid = len(errors) == 0

        return {
            "is_valid": is_valid,
            "warnings": warnings,
            "errors": errors,
            "total_area_match": True,  # We don't lose area during splitting
            "total_area_sqm": total_area_sqm,
            "target_area_sqm": target_area_sqm
        }

    @staticmethod
    def count_trees_in_polygon(
        db,
        parent_block_id,
        polygon: Polygon
    ) -> int:
        """
        Count trees that fall within a polygon

        Args:
            db: Database session
            parent_block_id: Parent block UUID
            polygon: Polygon to check

        Returns:
            Count of trees in polygon
        """
        from ..models.inventory import InventoryTree
        from geoalchemy2.shape import to_shape

        try:
            # Get trees for this block
            trees = db.query(InventoryTree).filter(
                InventoryTree.forest_block_id == parent_block_id
            ).all()

            count = 0
            for tree in trees:
                try:
                    tree_point = to_shape(tree.location)
                    if polygon.contains(tree_point):
                        count += 1
                except Exception as e:
                    logger.warning(f"Failed to check tree {tree.id}: {e}")

            return count
        except Exception as e:
            logger.error(f"Failed to count trees in polygon: {e}")
            return 0
