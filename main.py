from langchain_openai import OpenAIEmbeddings
from langchain_chroma import Chroma
import os, requests, time, sys, json, re
import plotly.graph_objects as go
from urllib.parse import urlencode
from dotenv import load_dotenv
import pandas as pd
from pathlib import Path


_BAD = re.compile(r'[\\/:*?"<>|]+')
def _safe_tag(name):
    s = _BAD.sub("_", name)
    s = re.sub(r"\s+", "_", s)
    s = s.strip("._")[:80] or "value"
    return s

def filter_results(raw_path, characteristicName):

    safe = _safe_tag(characteristicName)
    ResponseDataFolder = os.path.dirname(raw_path)
    filtered_path = os.path.join(ResponseDataFolder, f"filtered_result_{safe}.csv")

    cols = ["ActivityStartDate", "ResultMeasureValue"]

    try:
        df = pd.read_csv(raw_path, usecols=lambda c: c in cols)
    except:
        df = pd.read_csv(raw_path)
        df = df[[c for c in cols if c in df.columns]]

    #Drop rows missing critical data
    df = df.dropna(subset=["ActivityStartDate", "ResultMeasureValue"])

    #Check if there are sufficient data points
    if len(df) <= 3:
        print(f"<dev> Insufficient data for {characteristicName}: only {len(df)} data points found. Skipping...")
        os.remove(raw_path)
        return None

    #Deletes initial csv
    os.remove(raw_path)

    #Save
    df.to_csv(filtered_path, index=False)
    print(f"<dev> Filtered file saved to: {filtered_path}")
    return filtered_path

def create_chart(characteristicName: str, input_path: str) -> str:

    # Read the filtered CSV file
    safe = _safe_tag(characteristicName)
    
    if not os.path.exists(input_path):
        print(f"Error: File not found at {input_path}")
        return
    
    # Load data
    df = pd.read_csv(input_path)
    
    # Convert ActivityStartDate to datetime for proper sorting
    df['ActivityStartDate'] = pd.to_datetime(df['ActivityStartDate'])
    
    # Convert ResultMeasureValue to numeric, handling non-numeric values
    df['ResultMeasureValue'] = pd.to_numeric(df['ResultMeasureValue'], errors='coerce')
    
    # Drop rows with NaN values after conversion
    df = df.dropna(subset=['ActivityStartDate', 'ResultMeasureValue'])
    
    # Sort by date
    df = df.sort_values('ActivityStartDate')
    
    print(f"Chart {characteristicName} has {len(df)} data points")
    print(f"Date range: {df['ActivityStartDate'].min()} to {df['ActivityStartDate'].max()}")
    print(f"Value range: {df['ResultMeasureValue'].min()} to {df['ResultMeasureValue'].max()}")
    
    # Get min and max values for y-axis range
    y_min = df['ResultMeasureValue'].min()
    y_max = df['ResultMeasureValue'].max()
    
    # Create the plot
    fig = go.Figure()
    
    # Add line plot
    fig.add_trace(go.Scatter(
        x=df['ActivityStartDate'],
        y=df['ResultMeasureValue'],
        mode='lines',
        line=dict(
            color='blue',
            width=1.5
        ),
        name='Measurements'
    ))
    
    # Update layout
    fig.update_layout(
        title=f'Result Measure Value Over Time for {characteristicName}',
        xaxis_title='Activity Start Date',
        yaxis_title='Result Measure Value',
        yaxis=dict(
            range=[y_min, y_max]
        ),
        hovermode='closest',
        template='plotly_white',
        width=1200,
        height=600
    )
    
    # Save to HTML file
    output_path = os.path.join(os.getcwd(), f"chart_{safe}.html")
    fig.write_html(output_path)
    
    print("Chart Created!")

def fetch_API(inVar, inVar2):
    url = "https://www.waterqualitydata.us/data/Result/search?"

    params = {
        "characteristicName": inVar,
        "bBox": "-98.5,17.8,-80,31",
        "startDateLo": inVar2,
        "mimeType": "csv"
    }

    #Creates URL
    full_url = url + urlencode(params, safe=',')


    #Creates ResponseData directory if it doesn't exist
    target_dir = os.path.join(os.getcwd(), "ResponseData")
    os.makedirs(target_dir, exist_ok=True)

    safe = _safe_tag(inVar)
    filename = f"result_{safe}.csv"
    raw_path = os.path.join(target_dir, filename)

    response = requests.get(full_url)
    if response.status_code != 200:
        print(f"Error Code: {response.status_code}")
        return ""

    with open(raw_path, "wb") as f:
        f.write(response.content)
    print(f"Saved to path: {raw_path}")

    return raw_path

def search(inVar):
# 1) load values
    path = Path("values_filtered.json")
    with path.open("r", encoding="utf-8") as f:
        data = json.load(f)
    values = [v["value"] for v in data.get("codes", [])]
    assert values, "values_filtered.json has no 'codes' or is empty"
    
    #-=+=--=+=-
    # Load invalid values list if it exists
    invalid_path = Path("invalid.txt")
    invalid_values = set()
    if invalid_path.exists():
        with invalid_path.open("r", encoding="utf-8") as f:
            invalid_values = set(line.strip() for line in f if line.strip())
        print(f"Loaded {len(invalid_values)} invalid characteristic names to exclude")
    
    # Filter out invalid values
    values = [v for v in values if v not in invalid_values]
    assert values, "No valid values remaining after filtering"
    #-=+=--=+=-

    # 2) embeddings
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    assert api_key, "OPENAI_API_KEY not set"
    embeddings = OpenAIEmbeddings(model="text-embedding-3-small", openai_api_key=api_key)

    # 3) vector store
    persist_dir = "chroma_values_store"
    print("Creating chroma value storage...")
    vectorstore = Chroma.from_texts(values, embeddings, persist_directory=persist_dir)

    # 4) query
    def find_related(scene: str, top_n: int = 10):
        docs = vectorstore.similarity_search(scene, k=top_n)
        return [d.page_content for d in docs]

    scene = inVar
    results = find_related(scene, 20)
    results_list = [r for r in results]
    return results_list


    


def __init__():
    scenario = input("Input scenario here: ")
    results_list = search(scenario)
    print(f"<dev> This is the Results List: {results_list}")

    for i in results_list:
        print(f"<dev> STEP 1: Running fetch_API with characteristicname: {i}")
        raw_path = fetch_API(i, "01-01-1980")
        if not raw_path:
            continue

        print(f"<dev> STEP 2: Running filter_results for {i}")
        filtered_path = filter_results(raw_path, i)
        if not filtered_path:
            continue

        print(f"<dev> STEP 3 Running create_chart for {i}")
        create_chart(i, filtered_path)
        

if __name__ == "__main__":

    __init__()