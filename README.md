# libf_python_project
LIBF MSc Computer Science -- Python Programming Project

An object oriented Python system to take a KiCAD PCB and export
suitable files for use with PCBA capabilities from JLCPCB

# Quick testing (assuming a Linux system, with KiCad installed)

1. Download the code from GitHub
2. cd into the libf_python_project/plugin directory
3. Run: ./libf_plugin.py ../sample/sample_board.kicad_pcb
4. cd back into the main directory: cd ..
5. Run: ./process_files.py sample
6. out_bom.csv and out_cpl.csv will be created in this directory

# Plugin

The plugin can be installed in KiCad by copying or linking the plugin directory 
to your kicad scripting/plugins directory.

When you restart (or refresh the plugins) you will see a button with the L from
the LIFB logo on the toolbar. This will execute the plugin against the current
PCB.

Alternatively you can execute the plugin from the command-line if you provide
a suitable .kicad_pcb file to run against.

The board.csv and components.csv files will be created in the same directory as
the board file.

# Main Processing

The main script can be executed without KiCad being installed and can use the
sample board.csv and component.csv files included with this archive.

Usage: ./process_files.py <directory_with_csv_files_in>

So to use the sample board, you can use the following:

./process_files.py ./sample

This will produce an out_bom.csv and an out_cpl.csv file in the current directory.

