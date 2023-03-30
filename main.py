# We will import all required libraries that allows us to connect to the data source to pull data
from sodapy import Socrata
import requests
from requests.auth import HTTPBasicAuth
import json
import argparse
import sys
import os

# Now we create a parser where we can add our arguments as the input
parser = argparse.ArgumentParser(description='Fire Data NYC')
# In the parse, we have two arguments to add.
# The first one is a required argument for the program to run. If page_size is not passed in, don’t let the program to run
parser.add_argument('--page_size', type=int, help='how many rows to get per page', required=True)
# The second one is an optional argument for the program to run. It means that with or without it your program should be able to work.
parser.add_argument('--num_pages', type=int, help='how many pages to get in total')
# Take the command line arguments passed in (sys.argv) and pass them through the parser.
# Then you will end up with variables that contains page size and num pages.
args = parser.parse_args(sys.argv[1:])
print(args)


#Now we set our input for our program to run 
INDEX_NAME=os.environ["INDEX_NAME"]
DATASET_ID=os.environ["DATASET_ID"] 
APP_TOKEN=os.environ["APP_TOKEN"] 
ES_HOST=os.environ["ES_HOST"] 
ES_USERNAME=os.environ["ES_USERNAME"] 
ES_PASSWORD=os.environ["ES_PASSWORD"] 

#Next, set a function to create an index first
if __name__ == '__main__':
    try: 
        resp = requests.put(f"{ES_HOST}/{INDEX_NAME}", auth=HTTPBasicAuth(ES_USERNAME, ES_PASSWORD),
            json={ 
                "settings": {
                    "number_of_shards": 1,
                    "number_of_replicas": 1 
                },
                #Even though it is not for sure that the data will come clean, we are specifying the columns and our data 
                "mappings": {
                    "properties": { 
                        "starfire_incident_id": {"type": "float"}, 
                        "incident_datetime": {"type": "date"}, 
                        "incident_response_seconds_qy": {"type": "float"}, 
                        "incident_borough": {"type": "keyword"}, 
                        "incident_classification": {"type": "keyword"},
                    }
                },
            }
        )        
        resp.raise_for_status()  # We add this to see if it returns an HTTPError object if an error has occurred during the process. 

        
    #Now, if we add another put() request after creating an index, the pogram will give an error, so in order to avoid it we use a try and exception here. Because if the index is already created, it will see as an exception and continue the program.
    except Exception as e:
        print("Index already exists! Skipping")   
    
    #Now, since our index is created, we upload our data to Elasticsearch by using a for loop.
    #We use client to get the data from the datasource using our ap token and alos set a timeout at 10000 seconds
    #We use offset for continuity of our data
    #And add a where clause to get the data where starfire_incident_id and incident_datetime are not null
    for page in range(0, args.num_pages):
        client = Socrata("data.cityofnewyork.us", APP_TOKEN, timeout=10000) 
        rows = client.get(DATASET_ID,limit=args.page_size, offset=page*args.page_size, where="starfire_incident_id IS NOT NULL AND incident_datetime IS NOT NULL")
        es_rows=[] #we stoe data into an empty array
        
        #Now instead of getting all the data from the source, we use a for loop and select the specific columns we want for our project and convert them to Elasticsearch
        for row in rows: 
            try:
                # Convert
                es_row = {}
                es_row["starfire_incident_id"] = row["starfire_incident_id"]
                es_row["incident_datetime"] = row["incident_datetime"]
                es_row["incident_response_seconds_qy"] = row["incident_response_seconds_qy"]
                es_row["incident_borough"] = row["incident_borough"]
                es_row["incident_classification"] = row["incident_classification"]
                #For some cases data might have N/A values and in this case the conversion will crash, so we put an exception here.
            except Exception as e:
                print (f"Error!: {e}, skipping row: {row}") 
                continue
            
            #Now we add the rows together
            es_rows.append(es_row) 
            
            #Next we need to buld upload the data to Elasticsearch onstead of doing it one by one using json
            bulk_upload_data = "" 
            for line in es_rows:
                action = '{"index": {"_index": "' + INDEX_NAME + '", "_type": "_doc", "_id": "' + line["starfire_incident_id"] + '"}}' 
                data = json.dumps(line)
                bulk_upload_data += f"{action}\n"
                bulk_upload_data += f"{data}\n"

            try:
                # Upload to Elasticsearch by creating a document 
                resp = requests.post(f"{ES_HOST}/_bulk",
                # We upload es_row to Elasticsearch
                        data=bulk_upload_data, auth=HTTPBasicAuth(ES_USERNAME, ES_PASSWORD), headers = {"Content-Type": "application/x-ndjson"}) 
                resp.raise_for_status() 
                print ('Done')
                
                # Use an exception here if it fails, so we skip that row and move on. 
            except Exception as e:
                print(f"Failed to insert in ES: {e}")
            
            
            
            
            
            
