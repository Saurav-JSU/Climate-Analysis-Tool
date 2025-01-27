"""
cmip6_visualizer.py
Enhanced visualization component for CMIP6 data with real-time updates
"""

import ee
import geemap
import ipywidgets as widgets
from ipywidgets import Layout, HTML
from IPython.display import display
import plotly.graph_objects as go
import numpy as np
from dataclasses import dataclass
from typing import List, Dict, Any, Optional, Tuple, Callable
from datetime import datetime
from src.cmip6_dataset import CMIP6Dataset, ScenarioType, TimeFrameType
from src.cmip6_indices import IndexCategory, IndexInfo

@dataclass
class VisualizationConfig:
    """Configuration for CMIP6 visualization"""
    center: Tuple[float, float] = (0, 0)  # Default center
    zoom: int = 2  # Default zoom
    height: str = '500px'  # Default height
    width: str = '400px'  # Default width
    
    def __post_init__(self):
        """Validate and set defaults if needed"""
        if not self.center or not isinstance(self.center, tuple):
            self.center = (0, 0)
        if not self.zoom or not isinstance(self.zoom, int):
            self.zoom = 2

class MapContainer:
    """Container for map and its associated widgets"""
    def __init__(self, title: str, start_year: int, end_year: int, config: VisualizationConfig):
        # Ensure valid center coordinates
        center = config.center if config.center else (0, 0)
        zoom = config.zoom if config.zoom else 2
        
        self.map = geemap.Map(
            center=center,
            zoom=zoom,
            layout=Layout(height=config.height, width=config.width)
        )
        
        # Create year dropdown
        self.year_dropdown = widgets.Dropdown(
            options=list(range(start_year, end_year + 1)),
            value=end_year,  # Set default to end year
            description='Year:',
            layout=Layout(width='200px')
        )
        
        # Create header with title and year selector
        self.header = widgets.VBox([
            HTML(f"<h4 style='text-align: center; margin: 5px;'>{title}</h4>"),
            self.year_dropdown
        ])
        
        self.map.add_widget(self.header, position='topleft')
        self.current_layer = None
        self.current_legend = None

    def clear_layers(self):
        """Clear all data layers while preserving base layer"""
        try:
            if self.current_layer:
                self.map.remove_layer(self.current_layer)
                self.current_layer = None
            if self.current_legend:
                self.map.remove_control(self.current_legend)
                self.current_legend = None
        except Exception as e:
            print(f"Warning: Error clearing layers: {str(e)}")
            
    def update_bounds(self, bounds):
        """Safely update map bounds"""
        try:
            if bounds and hasattr(bounds, 'center'):
                self.map.center = bounds.center
                self.map.zoom = 6  # Default zoom level
        except Exception as e:
            print(f"Warning: Error updating bounds: {str(e)}")
            # Set default values if bounds update fails
            self.map.center = (0, 0)
            self.map.zoom = 2

class CMIP6Visualizer:
    """Enhanced visualizer for CMIP6 data and climate indices"""
    
    def __init__(self, dataset: Optional[CMIP6Dataset] = None):
        """Initialize visualizer"""
        self.dataset = dataset
        self.maps: List[MapContainer] = []
        self.sync_move = True
        self._loading_widget = HTML(
            value='<div style="color: #666;">Loading data...</div>',
            layout=Layout(display='none')
        )
        self.current_figure = None
        self.control_callbacks = {}
        self._error_widget = HTML(value="")
        # Add tracking for current analysis parameters
        self._current_analysis = {
            'index': None,
            'geometry': None,
            'dates': None
        }
        self.temporal_data = None
        self.status_label = None
        self._create_export_dirs()

    def _create_export_dirs(self):
        """Create necessary export directories"""
        import os
        base_dir = "CMIP6_Exports"
        if not os.path.exists(base_dir):
            os.makedirs(base_dir)

    def set_dataset(self, dataset: CMIP6Dataset) -> None:
        """Update the visualizer's dataset"""
        self.dataset = dataset

    def create_index_selector(self) -> widgets.VBox:
        """Create widgets for index selection"""
        if not self.dataset:
            self.dataset = CMIP6Dataset(
                CMIP6Dataset.list_available_models()[0],
                ScenarioType.SSP245
            )
        
        # Create category selection
        category_dropdown = widgets.Dropdown(
            options=[('Precipitation Indices', IndexCategory.PRECIPITATION),
                    ('Temperature Indices', IndexCategory.TEMPERATURE)],
            description='Category:',
            style={'description_width': 'initial'},
            layout=Layout(width='300px')
        )
        
        # Create index selection
        index_dropdown = widgets.Dropdown(
            options=self.dataset.get_available_indices(IndexCategory.PRECIPITATION),
            description='Index:',
            style={'description_width': 'initial'},
            layout=Layout(width='300px')
        )
        
        # Create info display
        info_display = HTML("")
        
        def update_indices(*args):
            category = category_dropdown.value
            index_dropdown.options = self.dataset.get_available_indices(category)
            if index_dropdown.options:
                index_dropdown.value = index_dropdown.options[0]
                update_info()
        
        def update_info(*args):
            index_name = index_dropdown.value
            if index_name:
                info = self.dataset.get_index_info(index_name)
                info_display.value = f"""
                <div style="padding: 10px; background: #f5f5f5; border-radius: 5px; margin: 10px 0;">
                    <h4 style="margin-top: 0;">{info.name}</h4>
                    <p>{info.description}</p>
                    <p><strong>Units:</strong> {info.units}</p>
                </div>
                """
                # Update current analysis when index changes
                self._current_analysis['index'] = index_name
        
        # Set up observers
        category_dropdown.observe(update_indices, names='value')
        index_dropdown.observe(update_info, names='value')
        
        # Create analyze button
        analyze_button = widgets.Button(
            description='Continue',
            button_style='primary',
            layout=Layout(width='150px', margin='10px 0px')
        )
        
        def on_analyze(b):
            if 'index_selected' in self.control_callbacks:
                self.control_callbacks['index_selected'](index_dropdown.value)
        
        analyze_button.on_click(on_analyze)
        
        # Update info for initial selection
        update_info()
        
        # Create container for controls
        controls_container = widgets.VBox([
            widgets.HBox([category_dropdown], layout=Layout(margin='10px 0')),
            widgets.HBox([index_dropdown], layout=Layout(margin='10px 0')),
            info_display,
            widgets.HBox([analyze_button], layout=Layout(margin='10px 0')),
            self._error_widget
        ], layout=Layout(
            padding='20px',
            border='1px solid #ddd',
            border_radius='5px'
        ))
        
        return controls_container

    def create_maps(self, config: VisualizationConfig = VisualizationConfig()) -> widgets.HBox:
        """Create three synchronized geemap instances with year selectors"""
        # Clean up existing maps
        for map_container in self.maps:
            map_container.clear_layers()
        self.maps = []
        
        # Define periods with year ranges
        periods = [
            ('Historical', 1980, 2014),
            ('Near Future', 2015, 2060),
            ('Far Future', 2061, 2100)
        ]
        
        try:
            for title, start_year, end_year in periods:
                # Ensure valid center coordinates
                center = config.center if config.center else (0, 0)
                zoom = config.zoom if config.zoom else 2
                
                map_container = MapContainer(title, start_year, end_year, config)
                
                # Set initial bounds safely
                map_container.map.center = center
                map_container.map.zoom = zoom
                
                self.maps.append(map_container)
            
            # Set up map synchronization with error handling
            def sync_maps(*args):
                if not self.sync_move:
                    return
                
                try:
                    triggered_map = args[0]['owner']
                    new_center = triggered_map.center
                    new_zoom = triggered_map.zoom
                    
                    if new_center and new_zoom:  # Only sync if valid values
                        for m in self.maps:
                            if m.map != triggered_map:
                                m.map.center = new_center
                                m.map.zoom = new_zoom
                except Exception as e:
                    print(f"Warning: Map sync error: {str(e)}")
            
            for m in self.maps:
                m.map.observe(sync_maps, names=['center', 'zoom'])
            
            return widgets.HBox([m.map for m in self.maps])
            
        except Exception as e:
            print(f"Error creating maps: {str(e)}")
            # Return an error message widget if map creation fails
            return widgets.HTML(
                value=f"""
                <div style="color: red; padding: 10px; border: 1px solid red; border-radius: 5px;">
                    <p>Error creating maps: {str(e)}</p>
                </div>
                """
            )

    def update_map_for_year(self, map_index: int, year: int, 
                           geometry: ee.Geometry, index_name: str,
                           vis_params: Dict) -> None:
        """Update specific map for selected year"""
        try:
            self.show_loading(True)
            
            # Get timeframe for this map
            timeframes = [TimeFrameType.HISTORICAL, 
                         TimeFrameType.NEAR_FUTURE, 
                         TimeFrameType.FAR_FUTURE]
            timeframe = timeframes[map_index]
            
            map_container = self.maps[map_index]
            map_container.clear_layers()
            
            # Calculate result for selected year
            result, index_info = self.calculate_year_result(
                timeframe, year, geometry, index_name
            )
            result = result.clip(geometry)
            
            # Add new layer
            map_container.current_layer = map_container.map.addLayer(
                result,
                vis_params,
                f"{index_info.name} ({year})"
            )
            
            # Add study area outline
            map_container.map.addLayer(
                geometry, 
                {'color': '000000', 'fillColor': '00000000'}, 
                'Study Area'
            )
            
            # Add legend
            map_container.current_legend = map_container.map.add_colorbar(
                vis_params['palette'],
                vis_params['min'],
                vis_params['max'],
                index_info.units,
                orientation='vertical',
                label=index_info.name
            )
            
        except Exception as e:
            self._error_widget.value = f"<p style='color: red'>Error updating map: {str(e)}</p>"
        finally:
            self.show_loading(False)

    def calculate_year_result(self, timeframe: TimeFrameType, 
                            year: int, geometry: ee.Geometry, 
                            index_name: str) -> Tuple[ee.Image, IndexInfo]:
        """Calculate index for a specific year"""
        start_date = f"{year}-01-01"
        end_date = f"{year}-12-31"
        return self.dataset.calculate_index(
            timeframe, start_date, end_date, geometry, index_name
        )

    def display_index(self, geometry: ee.Geometry,
                     index_name: str,
                     dates: Dict[str, Tuple[str, str]]) -> None:
        """Display climate index on maps"""
        try:
            if self.dataset is None:
                raise ValueError("No dataset available")
                
            self.show_loading(True)
            self._error_widget.value = ""
            
            # Update current analysis parameters
            self._current_analysis.update({
                'index': index_name,
                'geometry': geometry,
                'dates': dates
            })
            
            # Get index information and setup
            index_info = self.dataset.get_index_info(index_name)
            period_configs = [
                ('historical', TimeFrameType.HISTORICAL),
                ('near_future', TimeFrameType.NEAR_FUTURE),
                ('far_future', TimeFrameType.FAR_FUTURE)
            ]
            
            # Calculate initial results and get visualization parameters
            results = []
            initial_years = []
            
            for i, (period, timeframe) in enumerate(period_configs):
                year = int(dates[period][1][:4])
                initial_years.append(year)
                result, _ = self.calculate_year_result(
                    timeframe, year, geometry, index_name
                )
                results.append(result.clip(geometry))
            
            # Calculate visualization parameters
            vis_params = self.get_visualization_params(results, geometry, index_info)
            
            # Update maps
            for i in range(3):
                self.update_map_for_year(i, initial_years[i], geometry, index_name, vis_params)
                
                # Add year change handlers
                def make_year_handler(map_index):
                    def handle_year_change(change):
                        self.update_map_for_year(
                            map_index, 
                            change.new, 
                            geometry, 
                            index_name, 
                            vis_params
                        )
                    return handle_year_change
                
                self.maps[i].year_dropdown.observe(
                    make_year_handler(i),
                    names='value'
                )
            
        except Exception as e:
            self._error_widget.value = f"<p style='color: red'>Error displaying index: {str(e)}</p>"
        finally:
            self.show_loading(False)

    def get_visualization_params(self, results: List[ee.Image], 
                               geometry: ee.Geometry,
                               index_info: IndexInfo) -> Dict:
        """Get visualization parameters for the index"""
        try:
            # Calculate overall min/max
            min_max = ee.List([])
            for result in results:
                stats = result.reduceRegion(
                    reducer=ee.Reducer.minMax(),
                    geometry=geometry,
                    scale=10000,
                    maxPixels=1e9
                ).values()
                min_max = min_max.cat(stats)
            
            min_max_values = min_max.getInfo()
            overall_min = min(min_max_values)
            overall_max = max(min_max_values)
            
            return {
                'min': overall_min,
                'max': overall_max,
                'palette': index_info.palette or (
                    ['#313695', '#4575b4', '#74add1', '#abd9e9', '#e0f3f8',
                     '#ffffbf', '#fee090', '#fdae61', '#f46d43', '#d73027']
                    if index_info.category == IndexCategory.TEMPERATURE else
                    ['#fff5f0', '#fee0d2', '#fcbba1', '#fc9272', '#fb6a4a',
                     '#ef3b2c', '#cb181d', '#a50f15', '#67000d']
                ),
                'opacity': 0.8
            }
        except Exception as e:
            raise ValueError(f"Error calculating visualization parameters: {str(e)}")

    def create_temporal_plot(self, geometry: ee.Geometry,
                           index_name: str,
                           dates: Dict[str, Tuple[str, str]]) -> go.Figure:
        """Create temporal trend plot for index with optimized calculation"""
        try:
            if self.dataset is None:
                raise ValueError("No dataset available")
            
            index_info = self.dataset.get_index_info(index_name)
            
            # Configure plot settings
            plot_data = []
            colors = {
                'historical': {'line': 'rgb(31, 119, 180)', 'fill': 'rgba(31, 119, 180, 0.2)'},
                'near_future': {'line': 'rgb(255, 127, 14)', 'fill': 'rgba(255, 127, 14, 0.2)'},
                'far_future': {'line': 'rgb(44, 160, 44)', 'fill': 'rgba(44, 160, 44, 0.2)'}
            }
            
            timeframe_mapping = {
                'historical': TimeFrameType.HISTORICAL,
                'near_future': TimeFrameType.NEAR_FUTURE,
                'far_future': TimeFrameType.FAR_FUTURE
            }
            
            # Process each period in parallel using Earth Engine's batch computation
            for period, timeframe in timeframe_mapping.items():
                start_date, end_date = dates[period]
                years = list(range(int(start_date[:4]), int(end_date[:4]) + 1))
                
                # Create a feature collection for batch processing
                features = []
                for year in years:
                    feature = ee.Feature(None, {
                        'year': year,
                        'start_date': f"{year}-01-01",
                        'end_date': f"{year}-12-31"
                    })
                    features.append(feature)
                
                fc = ee.FeatureCollection(features)
                
                # Define computation for each year
                def calculate_year_stats(feature):
                    year = ee.Number(feature.get('year'))
                    start = ee.String(feature.get('start_date'))
                    end = ee.String(feature.get('end_date'))
                    
                    # Get the result for this year
                    result, _ = self.dataset.calculate_index(
                        timeframe, start, end, geometry, index_name
                    )
                    
                    # Calculate statistics
                    stats = result.reduceRegion(
                        reducer=ee.Reducer.mean(),
                        geometry=geometry,
                        scale=10000,
                        maxPixels=1e9
                    )
                    
                    return feature.set('value', stats.values().get(0))
                
                # Compute all years at once
                computed_fc = fc.map(calculate_year_stats)
                
                # Get values
                values_list = computed_fc.aggregate_array('value').getInfo()
                values = [float(v) if v is not None else None for v in values_list]
                
                # Create main line trace
                plot_data.append(go.Scatter(
                    x=years,
                    y=values,
                    mode='lines',
                    name=period.replace('_', ' ').title(),
                    line=dict(color=colors[period]['line'])
                ))
                
                # Add uncertainty range if we have values
                if values:
                    valid_values = [v for v in values if v is not None]
                    if valid_values:
                        std_dev = np.std(valid_values)
                        upper = [v + std_dev if v is not None else None for v in values]
                        lower = [v - std_dev if v is not None else None for v in values]
                        
                        plot_data.append(go.Scatter(
                            x=years + years[::-1],
                            y=upper + lower[::-1],
                            fill='toself',
                            fillcolor=colors[period]['fill'],
                            line=dict(color='rgba(255,255,255,0)'),
                            showlegend=False,
                            name=f'{period}_uncertainty'
                        ))
            
            # Create figure with all traces
            from plotly.graph_objs import FigureWidget
            fig = FigureWidget(data=plot_data)
            
            # Update layout
            fig.update_layout(
                title=f'Temporal Evolution of {index_info.name}',
                xaxis_title='Year',
                yaxis_title=f'{index_info.name} ({index_info.units})',
                showlegend=True,
                template='plotly_white',
                hovermode='x unified',
                width=900,
                height=500
            )
            self.current_figure = fig
            return fig
            
        except Exception as e:
            raise ValueError(f"Error creating temporal plot: {str(e)}")

    def store_temporal_data(self, data):
        """Store temporal data for export"""
        self.temporal_data = data

    def export_plot(self, b):
        """Export temporal plot data"""
        try:
            if not hasattr(self, 'current_figure') or self.current_figure is None:
                raise ValueError("No temporal data available")
            
            # Create directories
            import os
            export_dir = 'CMIP6_Exports/Plot_Data'
            os.makedirs(export_dir, exist_ok=True)
            
            # Extract data from figure
            data = {}
            for trace in self.current_figure.data:
                if trace.name and not trace.name.endswith('_uncertainty'):
                    data[trace.name] = {
                        'year': trace.x,
                        'value': trace.y
                    }
            
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f'{export_dir}/temporal_plot_{timestamp}.csv'
            
            # Convert to DataFrame and save
            import pandas as pd
            df = pd.DataFrame(data)
            df.to_csv(filename, index=False)
            
            self.status_label.value = f"<p style='color: green'>Plot data exported to {filename}</p>"
        except Exception as e:
            self.status_label.value = f"<p style='color: red'>Error exporting plot: {str(e)}</p>"

    def export_visible_maps(self, b):
        """Export currently visible maps"""
        try:
            if not self.dataset or not hasattr(self, 'maps'):
                raise ValueError("No maps available")

            self.status_label.value = "<p style='color: blue'>Preparing visible maps export...</p>"
            
            tasks_started = 0
            for i, period in enumerate(['historical', 'near_future', 'far_future']):
                if i < len(self.maps):
                    map_container = self.maps[i]
                    if hasattr(map_container, 'year_dropdown'):
                        selected_year = map_container.year_dropdown.value
                        print(f"Exporting {period} year {selected_year}")
                        self._export_single_year(period, selected_year, self.status_label)
                        tasks_started += 1
            
            if tasks_started > 0:
                self.status_label.value = f"<p style='color: green'>{tasks_started} export tasks started! Check GEE Tasks tab.</p>"
            else:
                self.status_label.value = "<p style='color: red'>No maps available to export</p>"
                
        except Exception as e:
            self.status_label.value = f"<p style='color: red'>Error: {str(e)}</p>"

    def export_all_years(self, b):
        """Export all years for current model/scenario"""
        try:
            if not self.dataset:
                raise ValueError("No dataset loaded")

            self.status_label.value = "<p style='color: blue'>Starting export for all years...</p>"
            
            periods = {
                'historical': range(1980, 2015),
                'near_future': range(2015, 2061),
                'far_future': range(2061, 2101)
            }
            
            tasks_started = 0
            for period, years in periods.items():
                for year in years:
                    print(f"Exporting {period} year {year}")
                    self._export_single_year(period, year, self.status_label)
                    tasks_started += 1
            
            self.status_label.value = f"<p style='color: green'>{tasks_started} export tasks started! Check GEE Tasks tab.</p>"
        except Exception as e:
            self.status_label.value = f"<p style='color: red'>Error: {str(e)}</p>"

    def export_all_models(self, b):
        """Export all years for all models"""
        try:
            if not self._current_analysis['geometry']:
                raise ValueError("No geometry defined")

            self.status_label.value = "<p style='color: blue'>Starting export for all models...</p>"
            
            tasks_started = 0
            for model in CMIP6Dataset.list_available_models():
                for scenario in [ScenarioType.SSP245, ScenarioType.SSP585]:
                    temp_dataset = CMIP6Dataset(model, scenario)
                    self.dataset = temp_dataset
                    
                    for period, years in {
                        'historical': range(1980, 2015),
                        'near_future': range(2015, 2061),
                        'far_future': range(2061, 2101)
                    }.items():
                        for year in years:
                            print(f"Exporting {model} {scenario.value} {period} {year}")
                            self._export_single_year(
                                period, year, 
                                self.status_label,
                                model_name=model,
                                scenario_name=scenario.value
                            )
                            tasks_started += 1
            
            self.status_label.value = f"<p style='color: green'>{tasks_started} export tasks started! Check GEE Tasks tab.</p>"
        except Exception as e:
            self.status_label.value = f"<p style='color: red'>Error: {str(e)}</p>"

    def create_export_controls(self) -> widgets.VBox:
        """Create enhanced export control widgets"""
        export_visible_btn = widgets.Button(
            description='Export Visible Years',
            button_style='info',
            layout=Layout(width='200px')
        )

        export_all_years_btn = widgets.Button(
            description='Export All Years (Current Model)',
            button_style='info',
            layout=Layout(width='250px')
        )

        export_all_models_btn = widgets.Button(
            description='Export All Years (All Models)',
            button_style='warning',
            layout=Layout(width='250px')
        )

        export_plot_btn = widgets.Button(
            description='Export Plot Data',
            button_style='success',
            layout=Layout(width='150px')
        )

        self.status_label = HTML(value="")

        def export_visible_maps(b):
            try:
                if not self.dataset or not hasattr(self, 'maps'):
                    raise ValueError("No maps available")

                self.status_label.value = "<p style='color: blue'>Preparing visible maps export...</p>"
                tasks_started = 0
                
                for i, period in enumerate(['historical', 'near_future', 'far_future']):
                    if i < len(self.maps):
                        map_container = self.maps[i]
                        selected_year = map_container.year_dropdown.value
                        self._export_single_year(period, selected_year, self.status_label)
                        tasks_started += 1
                
                self.status_label.value = f"<p style='color: green'>{tasks_started} export tasks started! Check GEE Tasks tab.</p>"
            except Exception as e:
                self.status_label.value = f"<p style='color: red'>Error: {str(e)}</p>"

        def export_all_years(b):
            try:
                if not self.dataset:
                    raise ValueError("No dataset loaded")

                self.status_label.value = "<p style='color: blue'>Starting export for all years...</p>"
                tasks_started = 0
                
                for period, years in {
                    'historical': range(1980, 2015),
                    'near_future': range(2015, 2061),
                    'far_future': range(2061, 2101)
                }.items():
                    for year in years:
                        self._export_single_year(period, year, self.status_label)
                        tasks_started += 1
                
                self.status_label.value = f"<p style='color: green'>{tasks_started} export tasks started!</p>"
            except Exception as e:
                self.status_label.value = f"<p style='color: red'>Error: {str(e)}</p>"

        def export_all_models(b):
            try:
                if not self._current_analysis['geometry']:
                    raise ValueError("No geometry defined")

                self.status_label.value = "<p style='color: blue'>Starting export for all models...</p>"
                tasks_started = 0
                
                for model in CMIP6Dataset.list_available_models():
                    for scenario in [ScenarioType.SSP245, ScenarioType.SSP585]:
                        temp_dataset = CMIP6Dataset(model, scenario)
                        self.dataset = temp_dataset
                        
                        for period, years in {
                            'historical': range(1980, 2015),
                            'near_future': range(2015, 2061),
                            'far_future': range(2061, 2101)
                        }.items():
                            for year in years:
                                self._export_single_year(
                                    period, year,
                                    self.status_label,
                                    model_name=model,
                                    scenario_name=scenario.value
                                )
                                tasks_started += 1
                
                self.status_label.value = f"<p style='color: green'>{tasks_started} export tasks started!</p>"
            except Exception as e:
                self.status_label.value = f"<p style='color: red'>Error: {str(e)}</p>"

        # Connect button handlers
        export_visible_btn.on_click(export_visible_maps)
        export_all_years_btn.on_click(export_all_years)
        export_all_models_btn.on_click(export_all_models)
        export_plot_btn.on_click(self.export_plot)

        return widgets.VBox([
            widgets.HTML("<h4>Export Options</h4>"),
            widgets.VBox([
                widgets.HBox([export_visible_btn, export_plot_btn],
                           layout=Layout(justify_content='space-around')),
                widgets.HBox([export_all_years_btn, export_all_models_btn],
                           layout=Layout(justify_content='space-around')),
                self.status_label
            ], layout=Layout(
                margin='20px 0',
                padding='10px',
                border='1px solid #ddd',
                border_radius='5px'
            ))
        ])

    def show_loading(self, show: bool = True) -> None:
        """Show or hide loading indicator"""
        self._loading_widget.layout.display = 'block' if show else 'none'

    def synchronize_maps(self, sync: bool = True) -> None:
        """Enable or disable map synchronization"""
        self.sync_move = sync

    def set_callback(self, event: str, callback: Callable) -> None:
        """Set callback for control panel events"""
        self.control_callbacks[event] = callback

    def cleanup(self):
        """Clean up resources"""
        for map_container in self.maps:
            map_container.clear_layers()
        self.maps = []

    def _export_single_year(self, period: str, year: int, status_label: HTML,
                           model_name: str = None, scenario_name: str = None) -> None:
        """Helper method to export a single year"""
        try:
            if not self._current_analysis:
                raise ValueError("No analysis configuration found")
                
            if not self._current_analysis['geometry']:
                raise ValueError("No geometry selected")
                
            timeframe = getattr(TimeFrameType, period.upper())
            start_date = f"{year}-01-01"
            end_date = f"{year}-12-31"

            # Get model and scenario names
            scenario_name = scenario_name or self.dataset.scenario.value
            model_name = model_name or self.dataset.model

            result, index_info = self.dataset.calculate_index(
                timeframe,
                start_date,
                end_date,
                self._current_analysis['geometry'],
                self._current_analysis['index']
            )

            geometry_bounds = self._current_analysis['geometry'].bounds()
            region = geometry_bounds.getInfo()['coordinates'][0]

            # Create export directory
            import os
            folder_path = f"CMIP6_Exports/{index_info.name}/{model_name}/{scenario_name}"
            os.makedirs(folder_path, exist_ok=True)

            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            
            task = ee.batch.Export.image.toDrive(
                image=result,
                description=f'cmip6_{index_info.name}_{model_name}_{scenario_name}_{period}_{year}_{timestamp}',
                folder=folder_path,
                scale=10000,
                region=region,
                maxPixels=1e9
            )
            
            task.start()
            print(f"Started export task for {year}")
            
        except Exception as e:
            print(f"Export error: {str(e)}")
            raise e