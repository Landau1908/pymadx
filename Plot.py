"""
Ploting script for madx TFS files using the pymadx Tfs class

"""

#need TFS but protect against already being imported in pymadx.__init__
#and therefore is a class and no longer a module - a consequence of
#the class having the same name as a file
try:
    from . import Tfs as _Tfs
except ImportError:
    import Tfs as _Tfs

from _General import CheckItsTfs as _CheckItsTfs

import numpy as _np
#protect against matplotlib import errors
try:
    import matplotlib         as _matplotlib
    import matplotlib.patches as _patches
    import matplotlib.pyplot  as _plt
except ImportError:
    print "pymadx.Plot -> WARNING - plotting will not work on this machine"
    print "matplotlib.pyplot doesn't exist"
    
class _My_Axes(_matplotlib.axes.Axes):
    """
    Inherit matplotlib.axes.Axes but override pan action for mouse.
    Only allow horizontal panning - useful for lattice axes.
    """
    name = "_My_Axes"
    def drag_pan(self, button, key, x, y):
        _matplotlib.axes.Axes.drag_pan(self, button, 'x', x, y) # pretend key=='x'

#register the new class of axes
_matplotlib.projections.register_projection(_My_Axes)

def _GetOpticalDataFromTfs(tfsobject):
    """
    Utility to pull out the relevant optical functions into a simple dictionary.
    """
    d = {}
    d['s']     = tfsobject.GetColumn('S')
    d['betx']  = tfsobject.GetColumn('BETX')
    d['bety']  = tfsobject.GetColumn('BETY')
    d['dispx'] = tfsobject.GetColumn('DX')
    d['dispy'] = tfsobject.GetColumn('DY')
    d['x']     = tfsobject.GetColumn('X')
    d['y']     = tfsobject.GetColumn('Y')
    return d

def PlotTfsCentroids(tfsfile, title='', outputfilename=None, machine=True):
    madx = _CheckItsTfs(tfsfile)
    d    = _GetOpticalDataFromTfs(madx)
    smax = madx.smax

    f    = _plt.figure(figsize=(11,5))
    axoptics = f.add_subplot(111)

    #optics plots
    axoptics.plot(d['s'],d['x'],'b-', label=r'$\mu_{x}$')
    axoptics.plot(d['s'],d['y'],'g-', label=r'$\mu_{y}$')
    axoptics.set_xlabel('S (m)')
    axoptics.set_ylabel(r'$\mu_{(x,y)}$ (m)')
    axoptics.legend(loc=0,fontsize='small') #best position

    #add lattice to plot
    if machine:
        AddMachineLatticeToFigure(f,madx)

    _plt.suptitle(title,size='x-large')
    
    if outputfilename != None:
        if '.' in outputfilename:
            outputfilename = outputfilename.split('.')[0]
        _plt.savefig(outputfilename+'.pdf')
        _plt.savefig(outputfilename+'.png')


def PlotTfsBeta(tfsfile, title='',outputfilename=None, machine=True, dispersion=False):
    """
    Plot sqrt(beta x,y) as a function of S. By default, a machine diagram is shown at
    the top of the plot.

    Optionally set dispersion=True to plot x dispersion as second axis.
    Optionally turn off machine overlay at top with machine=False
    Specify outputfilename (without extension) to save the plot as both pdf and png.
    """
    madx = _CheckItsTfs(tfsfile)
    d    = _GetOpticalDataFromTfs(madx)
    smax = madx.smax

    f    = _plt.figure(figsize=(11,5))
    axoptics = f.add_subplot(111)

    #optics plots
    axoptics.plot(d['s'],_np.sqrt(d['betx']),'b-', label='x')
    axoptics.plot(d['s'],_np.sqrt(d['bety']),'g-', label='y')
    if dispersion:
        axoptics.plot(-100,-100,'r--', label=r'$\mathrm{D}(x)$') #fake plot for legend
    axoptics.set_xlabel('S (m)')
    axoptics.set_ylabel(r'$\sqrt{\beta}$ ($\sqrt{\mathrm{m}}$)')
    axoptics.legend(loc=0,fontsize='small') #best position

    #plot dispersion - only in horizontal
    if dispersion:
        ax2 = axoptics.twinx()
        ax2.plot(d['s'],d['dispx'],'r--')
        ax2.set_ylabel('Dispersion (m)')

    #add lattice to plot
    if machine:
        AddMachineLatticeToFigure(f,madx)

    _plt.suptitle(title,size='x-large')
    
    if outputfilename != None:
        if '.' in outputfilename:
            outputfilename = outputfilename.split('.')[0]
        _plt.savefig(outputfilename+'.pdf')
        _plt.savefig(outputfilename+'.png')

def _SetMachineAxesStyle(ax):
    ax.get_xaxis().set_visible(False)
    ax.get_yaxis().set_visible(False)
    ax.spines['top'].set_visible(False)
    ax.spines['bottom'].set_visible(False)
    ax.spines['left'].set_visible(False)
    ax.spines['right'].set_visible(False)

def _PrepareMachineAxes(figure):
    # create new machine axis with proportions 6 : 1
    axmachine = figure.add_subplot(911, projection="_My_Axes")
    _SetMachineAxesStyle(axmachine)
    return axmachine

def _AdjustExistingAxes(figure, fraction=0.9, tightLayout=True):
    """
    Fraction is fraction of height all subplots will be after adjustment.
    Default is 0.9 for 90% of height. 
    """
    # we have to set tight layout before adjustment otherwise if called
    # later it will cause an overlap with the machine diagram
    if (tightLayout):
        _plt.tight_layout()
    
    axs = figure.get_axes()
    
    for ax in axs:
        bbox = ax.get_position()
        bbox.y0 = bbox.y0 * fraction
        bbox.y1 = bbox.y1 * fraction
        ax.set_position(bbox)  
        
def AddMachineLatticeToFigure(figure, tfsfile, tightLayout=True):
    """
    Add a diagram above the current graph in the figure that represents the
    accelerator based on a madx twiss file in tfs format.
    
    Note you can use matplotlib's gcf() 'get current figure' as an argument.

    AddMachineLatticeToFigure(gcf(), 'afile.tfs')

    A pymadx.Tfs class instance or a string specifying a tfs file can be
    supplied as the second argument interchangeably.

    """
    tfs = _CheckItsTfs(tfsfile) #load the machine description

    #check required keys
    requiredKeys = ['KEYWORD', 'S', 'L', 'K1L']
    okToProceed = all([key in tfs.columns for key in requiredKeys])
    if not okToProceed:
        print "The required columns aren't present in this tfs file"
        print "The required columns are: ", requiredKeys
        raise IOError

    axs = figure.get_axes() # get the existing graph
    
    axoptics  = figure.get_axes()[0]
    _AdjustExistingAxes(figure, tightLayout=tightLayout)
    axmachine = _PrepareMachineAxes(figure)
    
    _DrawMachineLattice(axmachine,tfs)

    #put callbacks for linked scrolling
    def MachineXlim(ax): 
        axmachine.set_autoscale_on(False)
        axoptics.set_xlim(axmachine.get_xlim())

    def Click(a) : 
        if a.button == 3 : 
            print 'Closest element: ',tfs.NameFromNearestS(a.xdata)

    axmachine.callbacks.connect('xlim_changed', MachineXlim)
    figure.canvas.mpl_connect('button_press_event', Click)

def _DrawMachineLattice(axesinstance,pymadxtfsobject):
    ax  = axesinstance #handy shortcut
    tfs = pymadxtfsobject
    
    #NOTE madx defines S as the end of the element by default
    #define temporary functions to draw individual objects
    def DrawBend(e,color='b',alpha=1.0):
        br = _patches.Rectangle((e['S']-e['L'],-0.1),e['L'],0.2,color=color,alpha=alpha)
        ax.add_patch(br)
    def DrawQuad(e,color='r',alpha=1.0):
        if e['K1L'] > 0 :
            qr = _patches.Rectangle((e['S']-e['L'],0),e['L'],0.2,color=color,alpha=alpha)
        elif e['K1L'] < 0: 
            qr = _patches.Rectangle((e['S']-e['L'],-0.2),e['L'],0.2,color=color,alpha=alpha)
        else:
            #quadrupole off
            qr = _patches.Rectangle((e['S']-e['L'],-0.1),e['L'],0.2,color='#B2B2B2',alpha=0.5) #a nice grey in hex
        ax.add_patch(qr)
    def DrawHex(e,color,alpha=1.0):
        s = e['S']-e['L']
        l = e['L']
        edges = _np.array([[s,-0.1],[s,0.1],[s+l/2.,0.13],[s+l,0.1],[s+l,-0.1],[s+l/2.,-0.13]])
        sr = _patches.Polygon(edges,color=color,fill=True,alpha=alpha)
        ax.add_patch(sr)
    def DrawRect(e,color,alpha=1.0):
        rect = _patches.Rectangle((e['S']-e['L'],-0.1),e['L'],0.2,color=color,alpha=alpha)
        ax.add_patch(rect)
    def DrawLine(e,color,alpha=1.0):
        ax.plot([e['S']-e['L'],e['S']-e['L']],[-0.2,0.2],'-',color=color,alpha=alpha)
            
    # plot beam line - make extra long in case of reversal - won't 
    ax.plot([tfs.smin,tfs.smax],[0,0],'k-',lw=1)
    ax.set_ylim(-0.2,0.2)
 
    # loop over elements and Draw on beamline
    for element in tfs:
        kw = element['KEYWORD']
        if kw == 'QUADRUPOLE': 
            DrawQuad(element, u'#d10000') #red
        elif kw == 'RBEND': 
            DrawBend(element, u'#0066cc') #blue
        elif kw == 'SBEND': 
            DrawBend(element, u'#0066cc') #blue
        elif kw == 'HKICKER':
            DrawRect(element, u'#4c33b2') #purple
        elif kw == 'VKICKER':
            DrawRect(element, u'#ba55d3') #medium orchid
        elif kw == 'RCOLLIMATOR': 
            DrawRect(element,'k')
        elif kw == 'ECOLLIMATOR': 
            DrawRect(element,'k')
        elif kw == 'SEXTUPOLE':
            DrawHex(element, u'#ffcc00') #yellow
        elif kw == 'OCTUPOLE':
            DrawHex(element, u'#00994c') #green
        elif kw == 'DRIFT':
            pass
        elif kw == 'MULTIPOLE':
            DrawHex(element,'grey',alpha=0.5)
        else:
            #unknown so make light in alpha
            if element['L'] > 1e-1:
                DrawRect(element,'#cccccc',alpha=0.1) #light grey
            else:
                #relatively short element - just draw a line
                DrawLine(element,'#cccccc',alpha=0.1)
