from hanziconv import HanziConv
import re
import os
from pathlib import Path

def convert_html_traditional_to_simplified(input_file, output_file):
    """
    Convert traditional Chinese text in a single HTML file to simplified Chinese.
    
    Args:
        input_file (str): Path to the input HTML file.
        output_file (str): Path to the output HTML file.
    """
    try:
        # Read the HTML file
        with open(input_file, 'r', encoding='utf-8') as file:
            html_content = file.read()

        # Function to convert only text parts, preserving HTML tags
        def convert_text(match):
            text = match.group(0)
            # Convert traditional Chinese to simplified Chinese
            return HanziConv.toSimplified(text)

        # Use regex to find text outside HTML tags
        pattern = r'>([^<]+)<'
        converted_content = re.sub(pattern, lambda m: convert_text(m), html_content)

        # Ensure output directory exists
        os.makedirs(os.path.dirname(output_file), exist_ok=True)

        # Write the converted content to the output file
        with open(output_file, 'w', encoding='utf-8') as file:
            file.write(converted_content)
        
        print(f"Converted {input_file} -> {output_file}")

    except FileNotFoundError:
        print(f"Error: The file {input_file} was not found.")
    except Exception as e:
        print(f"An error occurred while processing {input_file}: {str(e)}")

def process_html_directory(input_dir, output_dir):
    """
    Process all HTML files in the input directory and convert traditional Chinese to simplified.
    If the filename contains 'trad' (case-insensitive), replace it with 'simplified' in the output filename.
    
    Args:
        input_dir (str): Path to the directory containing input HTML files.
        output_dir (str): Path to the directory where output HTML files will be saved.
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)

    # Check if input directory exists
    if not input_path.exists():
        print(f"Error: Input directory {input_dir} does not exist.")
        return

    # Find all HTML files in the input directory
    html_files = list(input_path.glob("*.html")) + list(input_path.glob("*.htm"))

    if not html_files:
        print(f"No HTML files found in {input_dir}.")
        return

    for html_file in html_files:
        # Replace 'trad' with 'simplified' in filename (case-insensitive)
        output_filename = re.sub(r'trad', 'simplified', html_file.name, flags=re.IGNORECASE)
        # Define output file path
        relative_path = html_file.relative_to(input_path)
        output_file = output_path / output_filename

        # Convert the HTML file
        convert_html_traditional_to_simplified(html_file, output_file)

if __name__ == "__main__":
    input_directory = "/Users/vladimir.vasilenko/Yandex.Disk.localized/Languages/Китайский/wozhongwen/ChinesePod/1 Newbie/Scripts-trad.HTML/A0001trad-A0100trad"
    output_directory = "/Users/vladimir.vasilenko/Yandex.Disk.localized/Languages/Китайский/wozhongwen/ChinesePod/1 Newbie/Scripts-simplified.HTML/A0001simplified-A0100simplified"
    process_html_directory(input_directory, output_directory)
