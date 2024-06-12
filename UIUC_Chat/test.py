from pdf_process import process_pdf_file, parse_and_group_by_section
from SQLite import initialize_database, insert_data
import os
import json


# parser = argparse.ArgumentParser(description="Run S2ORC PDF2JSON")
# parser.add_argument("-i", "--input", default='/Users/jackhuang/Desktop/ai-ta-backend/UIUC_Chat/pdf/2303.14186.pdf', help="path to the input PDF file")
# parser.add_argument("-t", "--temp", default=BASE_TEMP_DIR, help="path to the temp dir for putting tei xml files")
# parser.add_argument("-o", "--output", default=BASE_OUTPUT_DIR, help="path to the output dir for putting json files")
# parser.add_argument("-k", "--keep", action='store_true')

# args = parser.parse_args()

# input_path = args.input
# temp_path = args.temp
# output_path = args.output
# keep_temp = args.keep

# start_time = time.time()

BASE_TEMP_DIR = 'temp'
BASE_OUTPUT_DIR = 'output'
temp_path = BASE_TEMP_DIR
output_path = BASE_OUTPUT_DIR
input_path = '/Users/jackhuang/Desktop/ai-ta-backend/UIUC_Chat/pdf/2303.14186v2.pdf'

grobid_config = {
    "grobid_server": 'https://grobid.kastan.ai',
    "batch_size": 1000,
    "sleep_time": 5,
    "timeout": 60
}

os.makedirs(temp_path, exist_ok=True)
os.makedirs(output_path, exist_ok=True)

output_file = process_pdf_file(input_path, temp_path, output_path, grobid_config)

#   runtime = round(time.time() - start_time, 3)
#   print("runtime: %s seconds " % (runtime))
print('process done.')

#   filepath = Path("/Users/jackhuang/Desktop/UIUC_Chat/allenai/output/2303.14186.json")
metadata, grouped_data, all_sections, total_tokens, avg_tokens_per_section, max_tokens_per_section = parse_and_group_by_section(output_file.name)
print('parse done.')
# print("Metadata:", metadata)
# print("Number of tokens per section:")
# for section in grouped_data:
#     print(f"Section {section['sec_num']} ({section['sec_title']}): {section['tokens']} tokens")
# # print(f"Page number: {section['page_num']}")
# print("All sections:", json.dumps(all_sections, indent=2))
# print("Total tokens:", total_tokens)
# print("Average tokens per section:", avg_tokens_per_section)
# print("Max tokens per section:", max_tokens_per_section)

db_path = 'articles.db'
initialize_database(db_path)

insert_data(metadata, total_tokens, grouped_data, db_path)