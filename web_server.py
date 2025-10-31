from flask import Flask, request, jsonify, send_from_directory, send_file
import os
import threading
import glob
import json
from pathlib import Path
import time
from main import search, fetch_API, filter_results, create_chart

app = Flask(__name__)

# Global variables to track analysis state
analysis_state = {
    'status': 'idle',  # idle, running, completed, error
    'message': 'Ready to analyze',
    'progress': 0,
    'total_characteristics': 0,
    'completed_charts': 0,
    'current_scenario': '',
    'error_message': ''
}

def reset_analysis_state():
    """Reset the analysis state for a new run"""
    global analysis_state
    analysis_state.update({
        'status': 'idle',
        'message': 'Ready to analyze',
        'progress': 0,
        'total_characteristics': 0,
        'completed_charts': 0,
        'current_scenario': '',
        'error_message': ''
    })

def update_analysis_status(status=None, message=None, progress=None, 
                          total_characteristics=None, completed_charts=None):
    """Update the analysis state"""
    global analysis_state
    if status:
        analysis_state['status'] = status
    if message:
        analysis_state['message'] = message
    if progress is not None:
        analysis_state['progress'] = progress
    if total_characteristics is not None:
        analysis_state['total_characteristics'] = total_characteristics
    if completed_charts is not None:
        analysis_state['completed_charts'] = completed_charts

def run_analysis(scenario):
    """Run the water quality analysis in a separate thread"""
    try:
        update_analysis_status(status='running', message='Creating chroma value storage...', progress=5)
        
        # Get related characteristics
        results_list = search(scenario)
        total_chars = len(results_list)
        
        update_analysis_status(
            message=f'Found {total_chars} related characteristics',
            progress=15,
            total_characteristics=total_chars
        )
        
        completed = 0
        
        for i, characteristic in enumerate(results_list):
            try:
                # Step 1: Fetch API data
                update_analysis_status(
                    message=f'STEP 1: Fetching data for {characteristic}',
                    progress=15 + (i * 80 / total_chars / 3)
                )
                
                raw_path = fetch_API(characteristic, "01-01-1980")
                if not raw_path:
                    continue
                
                # Step 2: Filter results
                update_analysis_status(
                    message=f'STEP 2: Filtering data for {characteristic}',
                    progress=15 + ((i * 80 / total_chars / 3) + (80 / total_chars / 3))
                )
                
                filtered_path = filter_results(raw_path, characteristic)
                if not filtered_path:
                    continue
                
                # Step 3: Create chart
                update_analysis_status(
                    message=f'STEP 3: Creating chart for {characteristic}',
                    progress=15 + ((i * 80 / total_chars / 3) + (2 * 80 / total_chars / 3))
                )
                
                create_chart(characteristic, filtered_path)
                completed += 1
                
                update_analysis_status(
                    completed_charts=completed,
                    progress=15 + ((i + 1) * 80 / total_chars)
                )
                
            except Exception as e:
                print(f"Error processing {characteristic}: {str(e)}")
                continue
        
        update_analysis_status(
            status='completed',
            message=f'Analysis completed! Generated {completed} charts.',
            progress=100
        )
        
    except Exception as e:
        update_analysis_status(
            status='error',
            message=f'Analysis failed: {str(e)}',
            progress=0
        )

@app.route('/')
def index():
    """Serve the main HTML page"""
    return send_file('index.html')

@app.route('/analyze', methods=['POST'])
def analyze():
    """Start the analysis process"""
    global analysis_state
    
    if analysis_state['status'] == 'running':
        return jsonify({'error': 'Analysis already in progress'}), 400
    
    data = request.get_json()
    scenario = data.get('scenario', '').strip()
    
    if not scenario:
        return jsonify({'error': 'No scenario provided'}), 400
    
    # Reset state and start analysis
    reset_analysis_state()
    analysis_state['current_scenario'] = scenario
    
    # Start analysis in a separate thread
    thread = threading.Thread(target=run_analysis, args=(scenario,))
    thread.daemon = True
    thread.start()
    
    return jsonify({'message': 'Analysis started', 'scenario': scenario})

@app.route('/status')
def get_status():
    """Get the current analysis status"""
    return jsonify(analysis_state)

@app.route('/charts')
def get_charts():
    """Get list of generated chart files"""
    chart_files = []
    
    # Look for HTML chart files in the current directory
    html_files = glob.glob('chart_*.html')
    
    for file_path in html_files:
        # Extract characteristic name from filename
        filename = os.path.basename(file_path)
        title = filename.replace('chart_', '').replace('.html', '').replace('_', ' ').title()
        
        chart_files.append({
            'title': title,
            'filename': filename,
            'url': f'/chart/{filename}'
        })
    
    return jsonify(chart_files)

@app.route('/chart/<filename>')
def serve_chart(filename):
    """Serve individual chart HTML files"""
    try:
        return send_file(filename)
    except FileNotFoundError:
        return "Chart not found", 404

@app.route('/static/<path:filename>')
def serve_static(filename):
    """Serve static files"""
    return send_from_directory('.', filename)

if __name__ == '__main__':
    print("Starting Gulf Water Quality Analysis Web Server...")
    print("Open your browser to: http://localhost:5000")
    print("Press Ctrl+C to stop the server")
    
    # Clean up any existing chart files at startup
    for chart_file in glob.glob('chart_*.html'):
        try:
            os.remove(chart_file)
        except:
            pass
    
    app.run(debug=True, host='0.0.0.0', port=5000)