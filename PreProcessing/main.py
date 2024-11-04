import pandas as pd
import matplotlib.pyplot as plt
import seaborn as sns
import ast
import polyline

def main():
    datasetFolder = 'Data/kaggleDatasets/'
    #df = pd.read_excel(datasetFolder+'Strava Running Data.xlsx', sheet_name='Sheet1')
    df = pd.read_csv(datasetFolder+'strava_data.csv')
    df['summary_polyline'] = df['map'].apply(extract_summary_polyline)
    coordsList =[]
    for poly in df['summary_polyline']:
        if poly is not None:
            coordsList.append(polyline.decode(poly, 5, geojson=True))
    print(coordsList[0:3])
    print(len(coordsList))
    print(len(coordsList[0]))
    df['decoded_polyline'] = df['summary_polyline'].apply(extractDecodedPolyline)
    print(df['decoded_polyline'])

def extractDecodedPolyline(value):
    if value is not None:
        return polyline.decode(value, 5 , geojson=True)
    else:
        return None


def addActivityToPlot(polyLi):
    coordinateList = polyline.decode(polyLi, 5, geojson=True)
    ys, xs = zip(*coordinateList)
    plt.plot(xs[0], ys[0], marker='o', color='g', ms=5)
    plt.plot(xs ,ys)
    plt.plot(xs[-1], ys[-1], marker='x', color='r', ms=5)
    
def plotStartEnd(df):
    df['start_latlng'] = df['start_latlng'].apply(parse_latlng)
    df['end_latlng'] = df['end_latlng'].apply(parse_latlng)
    df['latitude'] = df['start_latlng'].apply(extract_lat)
    df['longitude'] = df['start_latlng'].apply(extract_lng)
    df['latitude2'] = df['end_latlng'].apply(extract_lat)
    df['longitude2'] = df['end_latlng'].apply(extract_lng)
    scatterPlot(df, 'latitude', 'longitude')
    scatterPlot(df, 'latitude2', 'longitude2')
    seabornPlot(df, 'latitude', 'longitude')
    seabornPlot(df, 'latitude2', 'longitude2')
    plt.show()
    
def scatterPlot(df, column1, column2):
    plt.figure(figsize=(10, 8))
    plt.scatter(df[column1], df[column2], alpha=0.1, color='blue')  # Adjust alpha for transparency
    plt.xlabel('Longitude')
    plt.ylabel('Latitude')
    plt.title('Scatter Plot of Latitude and Longitude')
    #plt.show()



    # Plot heatmap using Seaborn
def seabornPlot(df, column1, column2):
    plt.figure(figsize=(10, 8))
    sns.kdeplot(data=df, x=column1, y=column2, cmap='viridis', fill=True)
    plt.xlabel('Longitude')
    plt.ylabel('Latitude')
    plt.title('Heatmap of Latitude and Longitude')
    #plt.show()

    
# Extract latitude and longitude values from the 'latlng' column
def extract_lat(value):
    if isinstance(value, list):
        try:
            return value[0]  # Extract longitude
        except:
            return None
    else:
        return None

def extract_lng(value):
    if isinstance(value, list):
        try:
            return value[1]  # Extract longitude
        except:
            return None
    else:
        return None
    

def parse_latlng(latlng_str):
    if pd.isna(latlng_str):
        return latlng_str  # Return NaN if the value is NaN
    else:
        return ast.literal_eval(latlng_str)
    
def extract_summary_polyline(value):
    if pd.notna(value):
        map = eval(value)
        return map['summary_polyline']

# Extract athlete IDs from the 'athlete' column
def extract_id(value):
    if pd.notna(value):
        try:
            return eval(value)['id']
        except:
            return None
    else:
        return None

# Plot histogram of athlete IDs
def plotHist(columnName, labelName = None):
    if labelName is None:
        labelName = columnName
    plt.hist(df[columnName].dropna(), bins=30, color='skyblue', edgecolor='black')
    plt.xlabel(labelName)
    plt.ylabel('Frequency')
    plt.title('Histogram of '+labelName)
    plt.grid(True)
    plt.show()

if __name__ == "__main__":
    main()
