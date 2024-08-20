#!/usr/bin/python3

from bokeh.plotting import figure, show     # for plotting
from math import nan                        # for Bokeh point lists
import csv                                  # csv import and export
import string                               # string manipulation
import pandas as pd                         # for visualisations
import re                                   # for rotation matching
import sys, os                              # path manipulation & exit
import unittest                             # for testing

#
# Helper function to convert from a KiCAD dimension (string) to
# a float value in mm
#
def kicad_num(v):
    """
    Convert a supplied KiCad dimension string (in microns) into 
    a float (in mm)
    """
    return(float(v)/1000000.0)

#
# Helper function to return the reference type from the given reference
#
# Could have used regex, but this seemed lighter weight.
#
def reftype(s):
    """
    Return the leading alpha part of the string, if there is none then
    return the whole string.
    """
    for i, c in enumerate(s):
        if (not c.isalpha()):
            if (i == 0):
                break;
            return s[:i].upper()
            
    return s

#
# We need to be able to support a list of footprints that need to be
# rotated where the KiCAD symbol orientation is differnt to the JLCPCD
# one.
#
class RotDB():
    """
    A Class for handling a rotations database
    """

    def __init__(self, filename):
        """
        Intialise the rotation db from the supplied filename
        """
        self.db = []
        with open(filename, "r") as fh:
            for line in fh:
                line = re.sub('#.*$', '', line)     # remove all after comment
                line = line.rstrip()                # remove trailing space and newline
                if (line == ""):
                    continue
                self.db.append(line.split())
    
    def possible_rotate(self, footprint):
        """
        Provide optional rotation information for a given footprint

        Examine the footprint name and see if we have a matching regular
        expression that matches, if it does return the rotation value
        otherwise return 0.
        """
        for rot in self.db:
            ex = rot[0]
            delta = float(rot[1])
            if (re.search(ex, footprint)):
                return delta
        return 0



class Board():
    """
    A class to encapsulate the outline of a board. We accept a series of points representing
    the polygon of the outline. This can then be shifted to a (0,0) position, and then the
    outline can be drawn.
    """
    
    def __init__(self):
        """
        TODO
        """
        self.minx = -1
        self.miny = -1
        self.xlist = []
        self.ylist = []

    def addPoint(self, x, y):
        """
        TODO
        """
        if (self.minx < 0 or x < self.minx):
            self.minx = x
        if (self.miny < 0 or y < self.miny):
            self.miny = y
        self.xlist.append(x)
        self.ylist.append(y)

    def shiftByAmount(self, movex, movey):
        """
        TODO
        """
        for index, x in enumerate(self.xlist):
            self.xlist[index] = x - movex;
        for index, y in enumerate(self.ylist):
            self.ylist[index] = y - movey;
        
    def shiftToZero(self):
        """
        TODO
        """
        self.shiftByAmount(self.minx, self.miny)

    def draw(self, plot, **kwargs):
        """
        TODO
        """
        plot.patch(self.xlist + [self.xlist[0]], self.ylist + [self.ylist[0]], **kwargs)


class Point():
    '''
    Helper class to group x and y co-ordinates
    '''
    def __init__(self, x, y):
        self.x = x
        self.y = y

class Size():
    '''
    Helper class to group width and height co-ordinates
    '''
    def __init__(self, w, h):
        self.w = w
        self.h = h
       

class Plottable():
    '''
    A class that puts a vaneer around the Bokeh plotting functions so that
    we can use percentage based co-ordinates for ease of scale drawing
    '''
    def __init__(self, x, y, w, h):
        self.origin = Point(x, y)
        self.size = Size(w, h)

    def block(self, plot, x, y, w, h, **kwargs):
        plot.block(x=self.origin.x + (self.size.w * x), y=self.origin.y + (self.size.h * y),
                width=self.size.w*w, height=self.size.h*h, **kwargs)

    def outline(self, plot):
        self.block(plot, 0, 0, 1, 1, line_color="#dddddd", fill_alpha=0.0, line_alpha=0.5, line_dash="dotted")

    def hatch(self, plot):
        # Used fixed (not relative) gap for this one...
        gap = 0.2
        plot.block(x=self.origin.x+gap, y=self.origin.y+gap, 
                    width=self.size.w-(gap*2), height=self.size.h-(gap*2),
                    hatch_color="green", hatch_pattern="diagonal_cross", hatch_weight=1, 
                    fill_alpha=0.0, line_alpha=0.0, hatch_scale=8)

    def line(self, plot, xlist, ylist, **kwargs):
        for i, x in enumerate(xlist):
            xlist[i] = self.origin.x + (self.size.w * x)
        for i, y in enumerate(ylist):
            ylist[i] = self.origin.y + (self.size.h * y)
        plot.line(xlist, ylist, **kwargs)

    def circle(self, plot, dia, **kwargs):
        mindim = min(self.size.w, self.size.h)
        plot.ellipse(x=self.origin.x + (self.size.w * 0.5), y=self.origin.y + (self.size.h * 0.5),
        width=mindim*dia, height=mindim*dia, **kwargs)

#
# TODO: exceptions...
#
class InvalidData(Exception):
   def __init___(self, exception_parameter, exception_message):
       super().__init__(self, exception_parameter, exception_message)



class Component():
    '''
    The base Component class serves a number of purposes...
    1. To keep all the KiCad data in relatively raw form
    2. To provide an interface to drawing for the board visualisation
    3. To provide the outputs needed for creating the assembly files
    4. To provide access for other metrics
    '''

    def __init__(self, board, fields):
        """
        Creates a component related to a given board.

        board is the board the component is on, this is used to properly scale drawing.
        fields contains all the necessary data to process the component
        """
        # First we check if the supplied fields are correct...
        for f in [ "ref", "value", "layer", "footprint", "lcsc", "x", "y", "rot",
                    "left", "top", "right", "bottom" ]:
            if not f in fields:
                raise InvalidData(f, "Field missing from supplied data")

        # Then store the fields we need for PCBA...
        self.ref = fields["ref"]
        self.value = fields["value"]
        self.layer = fields["layer"]
        self.footprint = fields["footprint"]
        self.lcsc = fields["lcsc"]
        self.x = float(fields["x"])
        self.y = -float(fields["y"])
        self.rot = float(fields["rot"])

        # Now we can add the Plottable for board visualisation, co-ordinates
        # converted to mm here...
        self.plotter = Plottable(
            kicad_num(fields["left"]) - board.minx,                     # x
            kicad_num(fields["top"]) - board.miny,                      # y
            kicad_num(fields["right"]) - kicad_num(fields["left"]),     # width
            kicad_num(fields["bottom"]) - kicad_num(fields["top"]))     # height
            
    def getName(self):
        """
        Return the name of the class (as we will be inherited)
        """
        return type(self).__name__

    def getBOMKey(self):
        """
        Return a key that uniquely identifies a BOM item
        """
        return self.value + "//" + self.footprint + "//" + self.lcsc

    def draw(self, plot):
        """
        Draw the component, just the ouline for the base Component.
        """
        self.plotter.outline(plot)


class Unknown(Component):
    def draw(self, plot):
        super().draw(plot)
        self.plotter.hatch(plot)


class Resistor(Component):
    def draw(self, plot):
        super().draw(plot)
        self.plotter.line(plot, 
                    [0.1, 0.3, 0.3, 0.7, 0.7, 0.9, nan, 0.7, 0.7, 0.3, 0.3],
                    [0.5, 0.5, 0.2, 0.2, 0.5, 0.5, nan, 0.5, 0.8, 0.8, 0.5],
                    color="yellow", line_width=1)

class FerriteBead(Resistor):
    def draw(self, plot):
        super().draw(plot)
        self.plotter.block(plot, 0.3, 0.2, 0.4, 0.6, color="yellow", 
                    hatch_color="yellow", hatch_pattern="vertical_wave", hatch_weight=1, 
                    fill_alpha=0.0, line_alpha=0.0, hatch_scale=3)

class Capacitor(Component):
    def draw(self, plot):
        super().draw(plot)
        self.plotter.line(plot, 
                    [0.1, 0.4, nan, 0.4, 0.4, nan, 0.6, 0.6, nan, 0.6, 0.9],
                    [0.5, 0.5, nan, 0.2, 0.8, nan, 0.2, 0.8, nan, 0.5, 0.5],
                    color="yellow", line_width=1)

class Transistor(Component):
    def draw(self, plot):
        super().draw(plot)
        self.plotter.circle(plot, 0.9, color="yellow", line_width=1);

class IC(Component):
    def draw(self, plot):
        super().draw(plot)

        xx = [ 0.3, 0.7, 0.7, 0.3, 0.3, nan ];      # Main box
        yy = [ 0.2, 0.2, 0.8, 0.8, 0.2, nan ];      # Main box
        for i in [ 0.3, 0.4, 0.5, 0.6, 0.7 ]:       # Add legs to both sides
            xx += [ 0.1, 0.3, nan ];
            yy += [ i, i, nan ];
            xx += [ 0.7, 0.9, nan ];
            yy += [ i, i, nan ];

        self.plotter.line(plot, xx, yy, color="yellow", line_width=1)


class Diode(Component):
    def draw(self, plot):
        super().draw(plot)
        self.plotter.line(plot,
                    [0.1, 0.3, 0.3, 0.7, 0.3, 0.3, nan, 0.7, 0.7, nan, 0.7, 0.9], 
                    [0.5, 0.5, 0.3, 0.5, 0.7, 0.5, nan, 0.3, 0.7, nan, 0.5, 0.5],
                    color="yellow", line_width=1)

class Dummy():
    """
    A dummy object to help with unit testing, we can manually set attributes to
    simulate an object that will have methods called.
    """
    def __init__(self):
        pass


class TestSupportingFunctions(unittest.TestCase):
    
    def test_kicad_num(self):
        self.assertEqual(kicad_num("123450000"), 123.45)
        self.assertEqual(kicad_num("0"), 0.00)
        self.assertEqual(kicad_num("-100500000"), -100.5)

    def test_reftype(self):
        self.assertEqual(reftype("R100"), "R")
        self.assertEqual(reftype("FB101"), "FB")
        self.assertEqual(reftype("q100"), "Q")
        self.assertEqual(reftype("+45"), "+45")
        self.assertEqual(reftype("ABC"), "ABC")
        self.assertEqual(reftype("XY99Z"), "XY")

    def test_rotdb(self):
        rdb = RotDB("rotations.cf")
        self.assertEqual(rdb.possible_rotate("non-matching-footprint"), 0)
        self.assertEqual(rdb.possible_rotate("SOT-23"), 180)
        self.assertEqual(rdb.possible_rotate("TDK_ATB"), 90)

    def test_board(self):
        board = Board()
        board.addPoint(200, 400)
        board.addPoint(200, 500)
        board.addPoint(300, 500)
        board.addPoint(300, 400)
        board.shiftToZero()
        self.assertEqual(board.xlist, [0, 0, 100, 100])
        self.assertEqual(board.ylist, [0, 100, 100, 0])

        def dummy_patch(xl, yl, **kwargs):
            self.assertEqual(xl, [0, 0, 100, 100, 0])
            self.assertEqual(yl, [0, 100, 100, 0, 0])
            self.assertEqual(kwargs["foo"], 100)
            self.assertEqual(kwargs["bar"], 200)

        plot = Dummy()
        setattr(plot, "patch", dummy_patch)
        board.draw(plot, foo=100, bar=200)

    def test_component(self):
        # Create Dummy() board for minx/miny values
        board = Dummy()
        setattr(board, "minx", 100)
        setattr(board, "miny", 200)
        fields = { "ref": "R100", "value": "1k", "layer": "F.Cu", "footprint": "0402", "lcsc": "", 
                    "x": str(500*1000000), "y": str(300*1000000), "rot": str(0),
                    "left": str(480*1000000), "top": str(290*1000000), 
                    "right": str(520*1000000), "bottom": str(310*1000000) }
        # Test Component is created...
        comp = Component(board, fields)
        self.assertIsNotNone(comp)
        # Check the re-alignment to the board is ok...
        self.assertEqual(comp.plotter.origin.x, 380)
        self.assertEqual(comp.plotter.origin.y, 90)
        self.assertEqual(comp.plotter.size.w, 40)
        self.assertEqual(comp.plotter.size.h, 20)
        # Check it fails if fields are wrong...
        del fields["footprint"]
        with self.assertRaises(InvalidData):
            comp = Component(board, fields)

#
# MAIN FROM HERE
#

def main():
    # First process the command line argument...
    # (1) command <path_to_input_file_dir>
    # (2) command -T [any other test arguments]
    if (len(sys.argv) < 2):
        print ("Usage: " + sys.argv[0] + " <-T [test_args] | path_to_input_file_dir>")
        sys.exit(1)

    # Kick off the unit tests...
    if (sys.argv[1] == "-T"):
        del sys.argv[1]             # -T confuses unittest!
        unittest.main()
        sys.exit(0)

    # Otherwise we are running against the input dir...
    file_path = sys.argv[1]

    if (not os.path.isdir(file_path)):
        print ("Error: " + path + " is not a directory.")
        sys.exit(1)

    board_file = os.path.join(file_path, "board.csv")
    component_file = os.path.join(file_path, "components.csv")

    if (not os.path.isfile(board_file)):
        print ("Error: board.csv not found in " + path)
        sys.exit(1)

    if (not os.path.isfile(component_file)):
        print ("Error: components.csv not found in " + path)
        sys.exit(1)

    #
    # Create the rotations database object...
    #
    rotdb = RotDB("rotations.cf")

    #
    # Support automatically mapping from reference to object type...
    mapping = { "FB": FerriteBead, "R": Resistor, "C": Capacitor, 
                "Q": Transistor, "U": IC, "D": Diode }

    #
    # Now create the Board object...
    #
    board = Board()
    with open(board_file) as bfile:
    # with open("/home/essele/kicad/sample/board.csv") as bfile:
        reader = csv.DictReader(bfile)
        for row in reader:
            board.addPoint(kicad_num(row["x"]), kicad_num(row["y"]))

        board.shiftToZero()

    #
    # Draw the board outline...
    #

    # create a new plot with a title and axis labels
    p = figure(title="PCB layout", x_axis_label="x (mm)", y_axis_label="y (mm)", match_aspect=True)
    board.draw(p, line_width=2, fill_color="#002d04", line_color="black")
    #p.line(board.xlist, board.ylist, legend_label="Board Outline", line_width=2)

    #
    # Now run through the components... prepare the visualations as well as the BOM/CPL info
    #

    # We will build a BOM dict as we go, combining like elements...
    bom = {}

    # Placement will be a list of dicts for output...
    placement = []

    # Data for pandas and reporting
    data = []

    with open(component_file) as cfile:
    # with open("/home/essele/kicad/sample/components.csv") as cfile:
        reader = csv.DictReader(cfile)
        for row in reader:
            # Get the reference type from the ref (i.e. R from R100)
            rt = reftype(row["ref"]);

            # Get the Class for that type of ref, otherwise an Unknown
            objclass = mapping.get(rt, Unknown)

            # Instantiate the object of the right class...
            c = objclass(board, row)

            # And draw the component for the board visualisation
            c.draw(p)

            # Now prepare the BOM info ... combine like components ...
            key = c.getBOMKey()
            if (not key in bom):
                bom[key] = { "Component": c.value, "Footprint": c.footprint, "JLCPCB": c.lcsc, "refs": [ c.ref ] }
            else:
                bom[key]["refs"].append(c.ref)

            # Now we can work on the placement information...
            layername = "top" if (c.layer == "F.Cu") else "bottom"
            rotation = (c.rot + rotdb.possible_rotate(c.footprint)) % 360

            placement.append({
                "Designator":   c.ref,
                "Mid X":        c.x / 1000000.0,
                "Mid Y":        -c.y / 1000000.0,        # y direction is reversed
                "Layer":        layername,
                "Rotation":     rotation,
            })

            data.append({
                "Reference":    c.ref,
                "Layer":        c.layer,
                "Type":         c.getName(),
                "Value":        c.value,
                "LCSC":         c.lcsc,
            })


    #
    # Now we can output the BOM...
    #
    with open("out_bom.csv", "w") as bomfile:
        writer = csv.DictWriter(bomfile, quoting=csv.QUOTE_ALL,
            fieldnames=["Component", "Designator", "Footprint", "JLCPCB"])
        writer.writeheader()
        for key, bominfo in bom.items():
            # Replace list of refs with comma separated string...
            bominfo["Designator"] = ",".join(bominfo["refs"])
            del bominfo["refs"]
            writer.writerow(bominfo)

    #
    # And the placement information
    #
    with open("out_cpl.csv", "w") as cplfile:
        writer = csv.DictWriter(cplfile, quoting=csv.QUOTE_NONNUMERIC,
            fieldnames=["Designator", "Mid X", "Mid Y", "Layer", "Rotation"])
        writer.writeheader();
        for item in placement:
            writer.writerow(item)

    #
    # Now we can produce the board visualisation...
    #
    show(p)

    #
    # Now generate a range of additional visualisations by creating a Pandas dataframe
    # from the data we have build up...
    #
    d = pd.DataFrame(data)
    print(d)


    #
    # Produce a bar chart showing how many of each component type are used in the
    # board...
    #
    p = figure(x_range=d["Type"].unique(), height=500, title="Bar Chart of Counts of Component Types",
                x_axis_label="Component Types", y_axis_label="Quantity")
    p.vbar(x=d["Type"].unique(), top=d["Type"].value_counts(), width=0.6)
    show(p)


#
# Test Cases
#



if __name__ == '__main__':
    main()

