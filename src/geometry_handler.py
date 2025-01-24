"""
geometry_handler.py
Handles geographic bounds and geometry operations for climate analysis
"""

from typing import List, Tuple, Optional, Dict, Any, Callable
import ee
import geemap
import geopandas as gpd
from ipywidgets import widgets, VBox, HBox, Layout
from ipyleaflet import DrawControl
import os
from shapely.geometry import box, mapping
from dataclasses import dataclass

@dataclass
class BoundsConfig:
    """Configuration for geographic bounds"""
    min_lon: float
    min_lat: float
    max_lon: float
    max_lat: float

    def to_list(self) -> List[float]:
        """Convert bounds to list format"""
        return [self.min_lon, self.min_lat, self.max_lon, self.max_lat]

    @property
    def center(self) -> Tuple[float, float]:
        """Calculate center point of bounds"""
        return ((self.min_lat + self.max_lat) / 2, 
                (self.min_lon + self.max_lon) / 2)

class GeometryHandler:
    """
    Handles geographic bounds and geometry operations for climate analysis
    """

    def __init__(self):
        """Initialize GeometryHandler"""
        self.bounds: Optional[BoundsConfig] = None
        self.current_map = None
        self.current_draw_control = None
        self._bounds_callback: Optional[Callable] = None
        self._geometry: Optional[ee.Geometry] = None

    def cleanup_map(self):
        """Clean up map resources"""
        try:
            if self.current_map is not None:
                # First remove the draw control if it exists
                if self.current_draw_control is not None:
                    self.current_map.remove_control(self.current_draw_control)
                
                # Clear all layers
                self.current_map.layers = self.current_map.layers[:1]  # Keep only the base layer
                
                # Remove all controls
                for control in self.current_map.controls:
                    self.current_map.remove_control(control)
                
                # Clear the map widget from the layout
                self.current_map.close()  # Close the widget
                
            # Reset references
            self.current_draw_control = None
            self.current_map = None
            self._geometry = None
            
        except Exception as e:
            print(f"Warning: Error during map cleanup - {str(e)}")
            # Even if there's an error, ensure references are cleared
            self.current_draw_control = None
            self.current_map = None
            self._geometry = None
            
    def initialize_map(self, center: Tuple[float, float] = (32.3, -90.18), 
                      zoom: int = 6) -> widgets.VBox:
        """Initialize map for drawing bounds"""
        # Clean up existing map if any
        self.cleanup_map()
        
        # Create new map
        self.current_map = geemap.Map(center=center, zoom=zoom,
                                    layout=Layout(width='800px', height='600px'))
            
        self.current_draw_control = DrawControl(
            rectangle={
                "shapeOptions": {
                    "color": "#0000FF",
                    "fillOpacity": 0.1
                }
            },
            polygon={}, circlemarker={}, circle={}, marker={}, polyline={},
            edit=True, remove=True
        )

        def handle_draw(target, action, geo_json):
            if action == 'created':
                coords = geo_json['geometry']['coordinates'][0]
                lons = [coord[0] for coord in coords]
                lats = [coord[1] for coord in coords]
                self.set_bounds(min(lons), min(lats), max(lons), max(lats))
                print("Area of interest drawn successfully!")

        self.current_draw_control.on_draw(handle_draw)
        self.current_map.add_control(self.current_draw_control)

        instructions = widgets.HTML(
            value="<p>Draw a rectangle on the map to define your area of interest.</p>"
        )

        clear_button = widgets.Button(
            description="Clear Drawing",
            layout=Layout(width='150px')
        )
        
        def clear_drawing(b):
            if self.current_draw_control:
                self.current_draw_control.clear()
            self.bounds = None
            self._geometry = None
            print("Drawing cleared. You can draw a new rectangle.")

        clear_button.on_click(clear_drawing)

        return VBox([
            instructions,
            self.current_map,
            clear_button
        ])

    def create_shapefile_widgets(self) -> VBox:
        """Create widgets for shapefile upload"""
        shapefile_label = widgets.HTML("<p>Enter the path to your shapefile:</p>")
        shapefile_input = widgets.Text(
            placeholder='Path to shapefile',
            description='Path:',
            layout=Layout(width='500px')
        )
        process_button = widgets.Button(description="Process Shapefile")

        def on_button_click(b):
            try:
                self.process_shapefile(shapefile_input.value)
            except Exception as e:
                print(f"Error processing shapefile: {e}")

        process_button.on_click(on_button_click)

        return VBox([
            shapefile_label,
            shapefile_input,
            process_button
        ])

    def create_bounds_widgets(self) -> VBox:
        """Create widgets for manual bounds input"""
        bounds_label = widgets.HTML("<p>Enter geometric bounds:</p>")
        min_lon_input = widgets.FloatText(
            description='Min Lon:',
            min=-180,
            max=180,
            step=0.1,
            layout=Layout(width='200px')
        )
        min_lat_input = widgets.FloatText(
            description='Min Lat:',
            min=-90,
            max=90,
            step=0.1,
            layout=Layout(width='200px')
        )
        max_lon_input = widgets.FloatText(
            description='Max Lon:',
            min=-180,
            max=180,
            step=0.1,
            layout=Layout(width='200px')
        )
        max_lat_input = widgets.FloatText(
            description='Max Lat:',
            min=-90,
            max=90,
            step=0.1,
            layout=Layout(width='200px')
        )
        submit_button = widgets.Button(description="Submit Bounds")

        def on_submit(b):
            try:
                self.set_bounds(
                    min_lon_input.value,
                    min_lat_input.value,
                    max_lon_input.value,
                    max_lat_input.value
                )
            except ValueError as e:
                print(f"Error: {e}")

        submit_button.on_click(on_submit)

        return VBox([
            bounds_label,
            HBox([min_lon_input, min_lat_input]),
            HBox([max_lon_input, max_lat_input]),
            submit_button
        ])

    def process_shapefile(self, filepath: str) -> None:
        """Process uploaded shapefile"""
        if not os.path.exists(filepath):
            raise ValueError("File not found")

        try:
            gdf = gpd.read_file(filepath)
            
            if gdf.crs is None:
                raise ValueError("Shapefile has no CRS defined")
                
            if gdf.crs.to_string() != "EPSG:4326":
                gdf = gdf.to_crs(epsg=4326)

            bounds = gdf.total_bounds
            self.set_bounds(bounds[0], bounds[1], bounds[2], bounds[3])

        except Exception as e:
            raise ValueError(f"Error processing shapefile: {str(e)}")

    def set_bounds(self, min_lon: float, min_lat: float, 
                  max_lon: float, max_lat: float) -> None:
        """Set geographic bounds"""
        if not (-180 <= min_lon <= 180 and -180 <= max_lon <= 180):
            raise ValueError("Longitude must be between -180 and 180")
        if not (-90 <= min_lat <= 90 and -90 <= max_lat <= 90):
            raise ValueError("Latitude must be between -90 and 90")
        if min_lon >= max_lon or min_lat >= max_lat:
            raise ValueError("Min values must be less than max values")

        self.bounds = BoundsConfig(min_lon, min_lat, max_lon, max_lat)
        self._geometry = ee.Geometry.Rectangle(self.bounds.to_list())

        if self._bounds_callback:
            self._bounds_callback(self.bounds)

    def get_ee_geometry(self) -> ee.Geometry:
        """Get Earth Engine geometry object"""
        if self._geometry is None:
            raise ValueError("No geometry defined")
        return self._geometry

    def set_bounds_callback(self, callback: Callable[[BoundsConfig], None]) -> None:
        """Set callback for bounds changes"""
        self._bounds_callback = callback

    def get_bounds_info(self) -> Dict[str, Any]:
        """Get information about current bounds"""
        if self.bounds is None:
            return {'status': 'No bounds set'}

        bounds_box = box(*self.bounds.to_list())
        return {
            'bounds': self.bounds.to_list(),
            'center': self.bounds.center,
            'area_km2': bounds_box.area * 111.32 * 111.32,
            'geometry': mapping(bounds_box)
        }