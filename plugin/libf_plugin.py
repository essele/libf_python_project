#!/usr/bin/python3.10

#
#
#
#
#
# In an ideal world you would do full processing in here rather than export CSV's
# for external processing, but to make testing easier, and for testing without KiCAD
# this allows for the provision of interim data.
# 
# Also, there are some limitations here if the KiCAD directory includes multiple
# designs as there would be a potential filename clash.
#

import pcbnew           # To access KiCAD functions
import os               # To manipulate filenames
import csv              # To output CSV files
import wx               # For in-kicad dialog box

class LIBFPlugin(pcbnew.ActionPlugin):
    ''' 
    Set the default values for the plugin, these control how the plugin appears
    within KiCad
    ''' 
    def defaults(self):
        self.name = "LIBF JLCPCBA BOM/Placement"
        self.category = "PCB Manufacture"
        self.description = "Create interim files for processing into JLCPCB's assembly service"
        self.show_toolbar_button = True
        self.icon_file_name = os.path.join(os.path.dirname(__file__), 'libf.png')
   
    '''
    The main entry point for the plugin
    '''
    def Run(self, board=None):
        #
        # Use the current board, unless one has been provided (for testing)
        #
        if board == None:
            board = pcbnew.GetBoard()

        #
        # Work out filenames, we want to put any files in the same place as the
        # board file
        #
        boardfile = board.GetFileName()
        path = os.path.dirname(boardfile)
#        name = os.path.splitext(os.path.basename(boardfile))[0]

        #
        # Try to work out the board outline
        #
        outline = pcbnew.SHAPE_POLY_SET();
        # TODO: catch error
        board.GetBoardPolygonOutlines(outline)

        linechain = outline.Outline(0);

        #
        # Now prepare to write the board.csv file which just contains a list of
        # points from the outline...
        #
        with open(os.path.join(path, "board.csv"), "w") as bfile:
            fieldnames = [ "x", "y" ]
            writer = csv.DictWriter(bfile, fieldnames=fieldnames)
            writer.writeheader()

            #
            # Get each point on the outline...
            #
            for point in linechain.CPoints():
                writer.writerow({"x": point.x, 'y': point.y })


        #
        # Now for each component we want to dump them with enough info
        # to do the JLCPCB stuff as well as the visualisations we need
        #
        with open(os.path.join(path, "components.csv"), "w") as cfile:
            fieldnames = [ "ref", "value", "layername", "footprint", "x", "y", "rot", "top", "left", "bottom", "right" ]
            writer = csv.DictWriter(cfile, fieldnames=fieldnames)
            writer.writeheader()

            for fp in board.GetFootprints():
                if (fp.IsExcludedFromBOM()):
                    continue

                #
                # Specific support for LCSC part numbers (if we have them)
                #
                if (fp.HasFieldByName("LCSC")):
                    lcsc = fp.GetFieldByName("LCSC")
                else:
                    lcsc = ""

                x = fp.GetPosition().x;
                y = fp.GetPosition().y;
                rot = fp.GetOrientation().AsDegrees();
                layer = fp.GetLayerName();
                ref = fp.GetReference();
                value = fp.GetValue();
                layername = "top" if (layer == "F.Cu") else "bottom"
                fpname = str(fp.GetFPID().GetLibItemName())

                bb = fp.GetBoundingBox()

                writer.writerow({
                    "ref":          ref,
                    "value":        value,
                    "layername":    layername,
                    "footprint":    fpname,
                    "x":            x,
                    "y":            y,
                    "rot":          rot,
                    "top":          bb.GetTop(),
                    "left":         bb.GetLeft(),
                    "bottom":       bb.GetBottom(),
                    "right":        bb.GetRight(),
                })

        msg = "LIBF Interim Files Created\n\n" + \
                    "BOARD: " + os.path.join(path, "board.csv") + "\n" + \
                    "COMPONENTS: " + os.path.join(path, "components.csv") + "\n"
        if(wx.App.Get() == None):
            print(msg)
        else:
            wx.MessageBox(msg, caption="JLCPCBA Plugin")

#
# Allow running from the command line for easier debugging...
#
if __name__ == "__main__":
    b = pcbnew.LoadBoard("/home/essele/kicad/sample/Yaugi Mini.kicad_pcb")
    LIBFPlugin().Run(board=b)

