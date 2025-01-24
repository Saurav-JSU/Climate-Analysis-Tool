"""
cmip6_analysis_tool.py
Enhanced main class for CMIP6 analysis tool with reordered workflow and complete functionality
"""

import ee
from typing import Optional, Dict, Any, List
from ipywidgets import widgets, VBox, HBox, Layout, HTML
from IPython.display import display, clear_output
from datetime import datetime

from src.geometry_handler import GeometryHandler
from src.cmip6_dataset import CMIP6Dataset, ScenarioType, TimeFrameType
from src.cmip6_visualizer import CMIP6Visualizer, VisualizationConfig
from src.time_period_handler import TimePeriodHandler, TimePeriodSelection
from src.cmip6_indices import IndexCategory

class CMIP6AnalysisTool:
    """
    Enhanced main class for CMIP6 analysis with reordered workflow
    """
    
    def __init__(self):
        """Initialize CMIP6AnalysisTool"""
        self.initialize_ee()
        self.geometry_handler = GeometryHandler()
        self.time_handler = TimePeriodHandler()
        self.visualizer = CMIP6Visualizer()
        self.dataset: Optional[CMIP6Dataset] = None
        self._current_analysis: Dict[str, Any] = {}
        self.results_container = widgets.VBox([])
        self.method_container = widgets.VBox([])

    def initialize_ee(self) -> None:
        """Initialize Google Earth Engine"""
        try:
            ee.Initialize()
        except:
            ee.Authenticate()
            ee.Initialize()

    def start(self) -> None:
        """Start the analysis tool with reordered workflow"""
        welcome_msg = HTML("""
        <div style='background-color: #f0f0f0; padding: 20px; border-radius: 5px; margin-bottom: 20px;'>
            <h2>Welcome to the CMIP6 Climate Analysis Tool</h2>
            <p>Follow these steps to analyze climate projections:</p>
            <ol>
                <li>Define your area of interest</li>
                <li>Select analysis time periods</li>
                <li>Choose climate indices</li>
                <li>Select model and scenario to view results</li>
            </ol>
        </div>
        """)
        display(welcome_msg)
        self.choose_input_type()

    def choose_input_type(self) -> None:
        """Create and display input type selection widgets"""
        header = HTML(
            value="""
            <h3>Step 1: Define Area of Interest</h3>
            <p>Select a method to define your area of interest:</p>
            """
        )
        
        input_type = widgets.RadioButtons(
            options=['Select method...', 'Draw on Map', 'Shapefile', 'Geometric Bounds'],
            value='Select method...',
            description='Input Type:',
            style={'description_width': 'initial'},
            layout=Layout(margin='10px 0px')
        )

        def update_method_widget(change):
            if change.new != change.old:
                self.geometry_handler.cleanup_map()
                self.method_container.children = []
                
                try:
                    if change.new == 'Draw on Map':
                        self.method_container.children = [self.geometry_handler.initialize_map()]
                    elif change.new == 'Shapefile':
                        self.method_container.children = [self.geometry_handler.create_shapefile_widgets()]
                    elif change.new == 'Geometric Bounds':
                        self.method_container.children = [self.geometry_handler.create_bounds_widgets()]
                except Exception as e:
                    self.method_container.children = [
                        HTML(value=f"<p style='color: red'>Error initializing {change.new}: {str(e)}</p>")
                    ]
        
        input_type.observe(update_method_widget, names='value')
        self.geometry_handler.set_bounds_callback(self._on_bounds_set)
        
        main_container = VBox([
            header,
            input_type,
            self.method_container
        ], layout=Layout(width='100%'))
        
        display(main_container)

    def _on_bounds_set(self, bounds) -> None:
        """Callback for when bounds are set"""
        clear_output(wait=True)
        print("✓ Area of interest set successfully!")
        self.select_time_periods()

    def select_time_periods(self) -> None:
        """Create and display time period selection widgets"""
        clear_output(wait=True)
        header = HTML("""
        <div style='margin-bottom: 20px;'>
            <h3>Step 2: Define Time Periods</h3>
            <p>Select the time periods for your analysis:</p>
        </div>
        """)
        display(header)
        
        self.time_handler.set_callback(self._on_periods_set)
        time_widgets = self.time_handler.create_selection_widgets()
        display(time_widgets)

    def _on_periods_set(self, selection: TimePeriodSelection) -> None:
        """Callback for when time periods are set"""
        self._current_analysis['time_periods'] = selection
        self.select_index()

    def select_index(self) -> None:
        """Create and display index selection widgets"""
        clear_output(wait=True)
        header = HTML("""
        <div style='margin-bottom: 20px;'>
            <h3>Step 3: Select Climate Index</h3>
            <p>Choose which climate index you want to analyze:</p>
        </div>
        """)
        display(header)
        
        index_selector = self.visualizer.create_index_selector()
        
        def on_index_selected(index_name: str):
            self._current_analysis['index'] = index_name
            self.create_model_scenario_interface()
        
        self.visualizer.set_callback('index_selected', on_index_selected)
        display(index_selector)

    def create_model_scenario_interface(self) -> None:
        """Create and display combined model/scenario selection and visualization interface"""
        clear_output(wait=True)
        
        header = HTML("""
        <div style='margin-bottom: 20px;'>
            <h3>Step 4: Select Model and View Results</h3>
            <p>Choose a climate model and scenario to view the analysis results.</p>
            <p>You can change the model or scenario at any time to compare different projections.</p>
            <p><em>Note: Initial calculation may take a few minutes. Progress will be shown below.</em></p>
        </div>
        """)
        
        # Create model and scenario dropdowns
        model_dropdown = widgets.Dropdown(
            options=CMIP6Dataset.list_available_models(),
            description='Model:',
            style={'description_width': 'initial'},
            layout=Layout(width='300px')
        )
        
        scenario_dropdown = widgets.Dropdown(
            options=[s.value for s in ScenarioType],
            description='Scenario:',
            style={'description_width': 'initial'},
            layout=Layout(width='300px')
        )
        
        # Loading indicator
        loading_indicator = HTML(
            value='',
            layout=Layout(margin='10px 0px')
        )
        
        def show_loading(show: bool = True):
            loading_indicator.value = """
                <div style="display: flex; align-items: center; margin: 10px 0;">
                    <div style="border: 4px solid #f3f3f3; border-top: 4px solid #3498db; 
                         border-radius: 50%; width: 24px; height: 24px; margin-right: 10px;
                         animation: spin 1s linear infinite;"></div>
                    <div>Computing results...</div>
                </div>
                <style>
                    @keyframes spin {
                        0% { transform: rotate(0deg); }
                        100% { transform: rotate(360deg); }
                    }
                </style>
            """ if show else ''

        def update_results(*args):
            # Create status container
            status_container = widgets.VBox([])
            plot_container = widgets.VBox([])  # Container for temporal plot
            self.results_container.children = [status_container]
            
            def show_status(message, is_error=False):
                """Update status message with loading spinner"""
                color = "#dc3545" if is_error else "#333333"
                spinner = "" if is_error else """
                    <div style="display: inline-block; width: 24px; height: 24px; border: 3px solid #f3f3f3;
                                border-top: 3px solid #3498db; border-radius: 50%; margin-right: 10px;
                                animation: spin 1s linear infinite;">
                    </div>
                    <style>
                        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
                    </style>
                """
                
                status_container.children = [HTML(f"""
                    <div style="padding: 15px; margin: 10px 0; background-color: #f8f9fa; 
                                border-radius: 5px; color: {color}; display: flex; align-items: center;">
                        {spinner}
                        <span>{message}</span>
                    </div>
                """)]
            
            try:
                show_status("Initializing dataset...")
                # Create new dataset
                self.dataset = CMIP6Dataset(
                    model_dropdown.value,
                    ScenarioType(scenario_dropdown.value)
                )
                self.visualizer.set_dataset(self.dataset)
                
                show_status("Preparing geographic data...")
                # Get required data
                geometry = self.geometry_handler.get_ee_geometry()
                dates = self.time_handler.get_formatted_dates()
                
                # Safely get bounds with fallback values
                try:
                    bounds = self.geometry_handler.bounds
                    center = bounds.center if bounds and hasattr(bounds, 'center') else (0, 0)
                    zoom = 6  # Default zoom level
                except Exception:
                    center = (0, 0)
                    zoom = 2
                
                show_status("Setting up visualization...")
                config = VisualizationConfig(
                    center=center,
                    zoom=zoom,
                    height='500px',
                    width='400px'
                )
                
                show_status("Creating map interface...")
                # Create maps with error handling
                try:
                    maps_container = self.visualizer.create_maps(config)
                except Exception as map_error:
                    show_status(f"Error creating maps: {str(map_error)}", is_error=True)
                    maps_container = widgets.HTML(
                        value="""
                        <div style="padding: 15px; background-color: #f8d7da; border: 1px solid #f5c6cb; 
                                border-radius: 5px; margin: 10px 0;">
                            <p style="color: #721c24; margin: 0;">Error creating maps. Trying to continue with other components...</p>
                        </div>
                        """
                    )
                
                show_status("Processing climate data...")
                try:
                    self.visualizer.display_index(
                        geometry,
                        self._current_analysis['index'],
                        dates
                    )
                except Exception as index_error:
                    show_status(f"Error displaying index: {str(index_error)}", is_error=True)
                
                export_controls = self.visualizer.create_export_controls()
                
                # Show maps and controls
                self.results_container.children = [
                    maps_container,
                    status_container,
                    plot_container,
                    export_controls
                ]
                
                # Update status for temporal analysis
                show_status("Generating temporal analysis (this may take a few minutes)...")
                
                def on_temporal_complete(change):
                    try:
                        # Generate plot
                        plot = self.visualizer.create_temporal_plot(
                            geometry,
                            self._current_analysis['index'],
                            dates
                        )
                        
                        # Convert Plotly figure to widget
                        from plotly.graph_objs import FigureWidget
                        plot_widget = FigureWidget(plot)
                        
                        # Update plot container
                        plot_container.children = [plot_widget]
                        
                        # Clear status once everything is done
                        status_container.children = []
                        
                    except Exception as e:
                        status_container.children = [HTML(f"""
                            <div style="padding: 15px; margin: 10px 0; background-color: #fff3cd; 
                                        border-radius: 5px; color: #856404;">
                                <p>Note: Temporal plot generation encountered an error: {str(e)}</p>
                                <p>However, you can still interact with the spatial analysis above.</p>
                            </div>
                        """)]
                
                # Start temporal analysis in background
                import threading
                threading.Thread(target=on_temporal_complete, args=(None,)).start()
                
            except Exception as e:
                error_message = str(e) if str(e) else "An unknown error occurred"
                show_status(f"Error: {error_message}", is_error=True)
        
        # Add change handlers
        model_dropdown.observe(update_results, names='value')
        scenario_dropdown.observe(update_results, names='value')
        
        # Create selection container
        selection_container = VBox([
            header,
            HBox([model_dropdown, scenario_dropdown], layout=Layout(margin='10px 0')),
            loading_indicator,
            self.results_container
        ])
        
        display(selection_container)
        
        # Trigger initial update
        update_results()

    def cleanup(self):
        """Cleanup resources"""
        if self.geometry_handler:
            self.geometry_handler.cleanup_map()
        
        if self.visualizer:
            # Add any visualizer cleanup if needed
            pass

if __name__ == "__main__":
    tool = CMIP6AnalysisTool()
    tool.start()