from ezauth.vault import VaultGCPCredentialGenerator
from google.cloud import bigquery
import os
import io
import json
import boto3
import pandas
import pandas_gbq
import xmltodict
import datetime

gcp_credentials = (
    VaultGCPCredentialGenerator.from_environment(
        "VAULT_URL", "VAULT_APP_ROLE_ID", "VAULT_APP_ROLE_SECRET"
    )
    .fetch_credentials(os.environ["VAULT_ETL_PATH"])
    .as_google_credentials()
)

S3_BUCKET = os.environ["S3_BUCKET"]
S3_KEY = os.environ["S3_KEY"]

s3 = boto3.client('s3')
s3_res = boto3.resource('s3')

s3_res_str = s3_res.Object(S3_BUCKET, S3_KEY).get()['Body'].read().decode('utf-8')

s3_cfg_json = json.loads(s3_res.Object(S3_BUCKET, "config/conf.json").get()['Body'].read().decode('utf-8'))

cfg_table_nm = s3_cfg_json.get("table_name")
cfg_dataset = s3_cfg_json.get("dataset")
cfg_dataset_xml = s3_cfg_json.get("dataset_xml")
cfg_operation = s3_cfg_json.get("operation")
cfg_header = s3_cfg_json.get("header")

pandas_gbq.context.credentials = gcp_credentials
pandas_gbq.context.project = cfg_dataset.split('.')[0]
bq = bigquery.Client(project=cfg_dataset.split('.')[0], credentials=gcp_credentials)
job_config_json = bigquery.LoadJobConfig(autodetect=True) # default to autodetect

def ls_bucket(pfx=''):
    objects = s3.list_objects_v2(Bucket=S3_BUCKET, Prefix=pfx)
    print("Contents of folder '{}' in bucket {}".format(pfx, S3_BUCKET))
    for obj in objects['Contents']:
        print(obj['Key'])
    
def bq_append_csv(table_id, data_frame):
    pandas_gbq.to_gbq(data_frame, table_id, if_exists='append')
    print("Appended CSV file {} to BigQuery".format(S3_KEY))

def bq_append_json_file_obj(table_id, json_file_object):
    job = bq.load_table_from_file(json_file_object, table_id, job_config=job_config_json)
    job.result()
    print("Appended JSON object {} to BigQuery".format(S3_KEY))

def bq_append_json(table_id, data_frame):
    job = bq.load_table_from_dataframe(data_frame, table_id, job_config=job_config_json)
    job.result()
    print("Appended JSON file {} to BigQuery".format(S3_KEY))

def add_suffix_before_extension(filename, suffix):
    return "".join(filename.split(".")[:-1]) + "_" + str(suffix).replace(" ", "_") + "." + filename.split(".")[-1]

def move_to_landed():
    dest_key = "landed"+S3_KEY[7:]
    dest_key = add_suffix_before_extension(dest_key, datetime.datetime.now())
    copy_source = {'Bucket': S3_BUCKET, 'Key': S3_KEY}
    s3.copy_object(Bucket = S3_BUCKET, CopySource = copy_source, Key = dest_key)
    s3.delete_object(Bucket = S3_BUCKET, Key = S3_KEY)
    print("Moved file {} to landed/".format(S3_KEY))

def wrap_brackets_if_needed(str_buffer):
    # pandas needs the json string wrapped in [] to load it
    if str_buffer[0] != "[":
        str_buffer = "[{}".format(str_buffer)
    if str_buffer[-1] != "]" and str_buffer[-2:] != "]\n" and str_buffer[-3:] != "]\r\n":
        str_buffer = "{}]".format(str_buffer)
    return str_buffer

if S3_KEY[-4:] == ".csv":
    if cfg_table_nm == "":
        cfg_table_nm = S3_KEY[8:-4]
    cfg_table_id = "{}.{}".format(cfg_dataset, cfg_table_nm)
    
    if cfg_header:
        df = pandas.read_csv(io.StringIO(s3_res_str), sep=",", header=0, low_memory=False)
    else:
        df = pandas.read_csv(io.StringIO(s3_res_str), sep=",", header=None, low_memory=False)
    t = datetime.datetime.now()
    df["row_gen_timestamp"] = [t] * df.shape[0]

    df = df.astype(str)

    if cfg_operation == "APPEND":
        print("Appending df to table {}".format(cfg_table_id))
        bq_append_csv(cfg_table_id, df)
        move_to_landed()
    else:
        print("Operation not supported: {}".format(cfg_operation))

elif S3_KEY[-5:] == ".json":
    if cfg_table_nm == "":
        cfg_table_nm = S3_KEY[8:-5]
    cfg_table_id = "{}.{}".format(cfg_dataset, cfg_table_nm)

    str_buffer = wrap_brackets_if_needed(s3_res_str)
    
    df = pandas.read_json(io.StringIO(str_buffer))
    df_norm = pandas.json_normalize(json.loads(str_buffer))

    t = datetime.datetime.now()
    df["row_gen_timestamp"] = [t] * df.shape[0]
    df_norm["row_gen_timestamp"] = [t] * df_norm.shape[0] # * df.shape[0]

    df = df.astype(str)

    if cfg_operation == "APPEND":
        bq_append_json(cfg_table_id, df_norm)
        move_to_landed()
    else:
        print("Operation not supported: {}".format(cfg_operation))

elif S3_KEY[-4:] == ".xml":
    if cfg_table_nm == "":
        cfg_table_nm = S3_KEY[8:-4]
    cfg_table_id = "{}.{}".format(cfg_dataset_xml, cfg_table_nm)
    
    jdatastring = json.dumps(xmltodict.parse(s3_res_str, attr_prefix='')) # list of dict
    jdatastring = jdatastring.replace("\n", " ") # remove newlines
    
    print("BEGIN JSON STRING")
    print(jdatastring)
    print("END JSON STRING")

    jfile = io.StringIO(jdatastring) # json.loads(jdatastring)

    job_config_json.source_format = bigquery.SourceFormat.NEWLINE_DELIMITED_JSON

    #df_norm = pandas.json_normalize(jdata)

    #t = datetime.datetime.now()
    #df_norm["row_gen_timestamp"] = [t] * df_norm.shape[0]

    # schema = pandas_gbq.schema.generate_bq_schema(df_norm)
    # schema = pandas_gbq.schema.add_default_nullable_mode(schema)
    # job_config_json.schema = [
    #     bigquery.SchemaField.from_api_repr(field) for field in schema["fields"]
    # ]

    if cfg_operation == "APPEND":
        bq_append_json_file_obj(cfg_table_id, jfile)
        move_to_landed()
    else:
        print("Operation not supported: {}".format(cfg_operation))

else:
    print("Invalid format: '{}' should be either JSON, CSV, or XML".format(S3_KEY))
