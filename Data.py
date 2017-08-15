import tarfile
import numpy as _np
import copy as _copy
import string as _string
import re as _re

from _General import GetSixTrackAperType as _GetSixTrackAperType
from _General import Cast as _Cast

#from pymadx.Plot import PlotTfsBeta as _PlotTfsBeta

try:
    import Plot as _Plot
except ImportError:
    pass

from copy import deepcopy

#object inheritance is only for type comparison

class Tfs(object):
    """
    MADX Tfs file reader

    >>> a = Tfs()
    >>> a.Load('myfile.tfs')
    >>> a.Load('myfile.tar.gz') -> extracts from tar file

    or 

    >>> a = Tfs("myfile.tfs")
    >>> b = Tfs("myfile.tar.gz")

    | `a` has data members:
    | header      - dictionary of header items
    | columns     - list of column names
    | formats     - list of format strings for each column
    | data        - dictionary of entries in tfs file by name string
    | sequence    - list of names in the order they appear in the file
    | nitems      - number of items in sequence

    NOTE: if no column "NAME" is found, integer indices are used instead

    See the various methods inside a to get different bits of information:
    
    >>> a.ReportPopulations?

    Examples:

    >>> a.['IP.1'] #returns dict for element named "IP.1"
    >>> a[:30]     #returns list of dicts for elements up to number 30
    >>> a[345]     #returns dict for element number 345 in sequence
    
    """
    def __init__(self,filename=None,**kwargs):
        object.__init__(self) #this allows type comparison for this class
        self.index       = []
        self.header      = {}
        self.columns     = []
        self.formats     = []
        self.data        = {}
        self.sequence    = []
        self.nitems      = 0
        self.nsegments   = 0
        self.segments    = []
        self.filename    = filename
        self.smax        = 0
        self.smin        = 0
        self._verbose    = False
        if 'verbose' in kwargs:
            self._verbose = kwargs['verbose']
        if type(filename) == str:
            self.Load(filename, self._verbose)
        elif type(filename) == Tfs:
            self._DeepCopy(filename)
        
    def Clear(self):
        """
        Empties all data structures in this instance.
        """
        self.__init__()
    
    def Load(self, filename, verbose=False):
        """
        >>> a = Tfs()
        >>> a.Load('filename.tfs')
        
        Read the tfs file and prepare data structures. If 'tar' or 'gz are in 
        the filename, the file will be opened still compressed.
        """
        if ('tar' in filename) or ('gz' in filename):
            print 'pymadx.Tfs.Load> zipped file'
            tar = tarfile.open(filename,'r')
            f = tar.extractfile(tar.firstmember)
        else:
            print 'pymadx.Tfs.Load> normal file'
            f = open(filename)
        
        #first pass at file - need to check if it has 'NAME' column
        #if it has name, use that, otherwise use an integer
        #find column names line
        for line in f:
            if not line.strip():
                continue #protection against empty lines being misidentified as column lines
            sl = line.strip('\n').split()
            if line[0] == '*':
                #name
                self.columns.extend(sl[1:]) #miss "*" from column names line
                if verbose:
                    print 'Columns will be:'
                    print self.columns
                break
        if 'NAME' in self.columns:
            usename = True #use the name
        else:
            usename = False #no name column - use an index
        self.columns =  [] #reset columns for proper data read in
        f.seek(0) #reset file back to the beginning for reading in data

        #segment specific stuff
        segment_i = 0 #actual segment number in data may not be zero counting - use this variable
        segment_name = 'NA'
        #always include segments - put as first column in data
        self.columns.append("SEGMENT")
        self.formats.extend("%d")
        self.columns.append("SEGMENTNAME")
        self.formats.extend("%s")

        namecolumnindex = 0
        
        #read in data
        for line in f:
            if not line.strip():
                continue #protect against empty lines, although they should not exist
            splitline = line.strip('\n').split()
            sl        = splitline #shortcut
            if line[0] == '@':
                #header
                self.header[sl[1]] = _Cast(sl[-1])
            elif line[0] == '*':
                #name
                self.columns.extend(sl[1:]) #miss *
                if "NAME" in self.columns:
                    namecolumnindex = self.columns.index("NAME")
            elif line[0] == '$':
                #format
                self.formats.extend(sl[1:]) #miss $
            elif '#' in line[0]:
                #segment line
                d = [_Cast(item) for item in sl[1:]]
                segment_i    = d[0]
                segment_name = d[-1]
                self.nsegments += 1 # keep tally of number of segments
                self.segments.append(segment_name)
            else:
                #data
                d = [_Cast(item) for item in sl]
                d.insert(0,segment_name) #prepend segment info
                d.insert(0,segment_i) #this one becomes the first item matching the column index
                if usename:
                    name = self._CheckName(d[namecolumnindex])
                else:
                    name = self.nitems
                self.sequence.append(name) # keep the name in sequence
                self.data[name] = d        # put in data dict by name
                self.nitems += 1           # keep tally of number of items
                
        f.close()
        
        #additional processing
        self.index = range(0,len(self.data),1)
        if 'S' in self.columns:
            self.smin = self[0]['S']
            self.smax = self[-1]['S']
            sindex = self.ColumnIndex('S')
            sEnd = self.GetColumn('S')  #calculating the mid points as the element
            sEnd = _np.insert(sEnd,0,0)
            sMid = (sEnd[:-1] + sEnd[1:])/2

            for i, name in enumerate(self.sequence):
                self.data[name].append(self.data[name][sindex]) # copy S to SORIGINAL
                self.data[name].append(sMid[i])
            self.columns.append('SORIGINAL')
            self.columns.append('SMID')
        else:
            self.smax = 0

        #Check to see if input Tfs is Sixtrack style (i.e no APERTYPE, and is instead implicit)
        if 'APER_1' in self.columns and 'APERTYPE' not in self.columns:
            self.columns.append('APERTYPE')

            for key, element in self.data.iteritems():
                aper1 = element[self.columns.index('APER_1')]
                aper2 = element[self.columns.index('APER_2')]
                aper3 = element[self.columns.index('APER_3')]
                aper4 = element[self.columns.index('APER_4')]
                apertype = _GetSixTrackAperType(aper1,aper2,aper3,aper4)

                element.append(apertype)

        self._CalculateSigma()
        self.names = self.columns

    def _CalculateSigma(self):
        if 'GAMMA' not in self.header:
            self.header['BETA'] = 1.0 # assume super relativistic
        else:
            self.header['BETA'] = _np.sqrt(1.0 - (1.0/(self.header['GAMMA']**2)))

        # check this file has the appropriate variables else, return without calculating
        # use a set to check if all variables are in a given list easily
        requiredVariablesB = set(['DX', 'DY', 'DPX', 'DPY', 'ALFX', 'ALFY', 'BETX', 'BETY'])
        if not requiredVariablesB.issubset(self.columns):
            return
        requiredVariablesH = set(['SIGE', 'EX', 'EY'])
        if not requiredVariablesH.issubset(self.header.keys()):
            return
        
        # get indices to the columns we'll need in the data
        dxindex   = self.ColumnIndex('DX')
        dyindex   = self.ColumnIndex('DY')
        dpxindex  = self.ColumnIndex('DPX')
        dpyindex  = self.ColumnIndex('DPY')
        alfxindex = self.ColumnIndex('ALFX')
        alfyindex = self.ColumnIndex('ALFY')
        betxindex = self.ColumnIndex('BETX')
        betyindex = self.ColumnIndex('BETY')

        # constants
        sige = self.header['SIGE']
        beta = self.header['BETA'] # relativistic beta
        ex   = self.header['EX']
        ey   = self.header['EY']
        self.columns.extend(['SIGMAX', 'SIGMAY', 'SIGMAXP', 'SIGMAYP'])
        for elementname in self.sequence:
            # beam size calculations (using relation deltaE/E = beta^2 * deltaP/P)
            d = self.data[elementname]
            xdispersionterm = (d[dxindex] * sige / beta)**2
            ydispersionterm = (d[dyindex] * sige / beta)**2
            sigx = _np.sqrt((d[betxindex] * ex) + xdispersionterm)
            sigy = _np.sqrt((d[betyindex] * ey) + ydispersionterm)
            d.append(sigx)
            d.append(sigy)

            # beam divergences (using relation x',y' = sqrt(gamma_x,y * emittance_x,y))
            gammax = (1.0 + d[alfxindex]**2) / d[betxindex] # twiss gamma
            gammay = (1.0 + d[alfyindex]**2) / d[betyindex]
            xdispersionterm = (d[dpxindex] * sige / beta)**2
            ydispersionterm = (d[dpyindex] * sige / beta)**2
            sigxp  = _np.sqrt((gammax * ex) + xdispersionterm)
            sigyp  = _np.sqrt((gammay * ey) + ydispersionterm)
            d.append(sigxp)
            d.append(sigyp)

    def __repr__(self):
        s =  ''
        s += 'pymadx.Tfs instance\n'
        s += str(self.nitems) + ' items in lattice\n'
        return s

    def __len__(self):
        return len(self.sequence)

    def __iter__(self):
        self._iterindex = -1
        return self

    def next(self):
        if self._iterindex == len(self.sequence)-1:
            raise StopIteration
        self._iterindex += 1
        return self.GetRowDict(self.sequence[self._iterindex])

    def __getitem__(self,index):
        #index can be a slice object, string or integer - deal with in this order
        #return single item or slice of lattice
        if type(index) == slice:
            start,stop,step = index.start, index.stop, index.step #note slices are immutable
            #test values incase of ':' use
            if step != None and type(step) != int:
                raise ValueError("Invalid step "+step)
            if start != None and stop != None and step != None:
                # [start:stop:step]
                start = self._EnsureItsAnIndex(start)
                stop  = self._EnsureItsAnIndex(stop)
            elif start != None and stop != None and step == None:
                # [start:stop]
                start = self._EnsureItsAnIndex(start)
                stop  = self._EnsureItsAnIndex(stop)
                step  = 1
            elif start == None and stop == None and step > 0:
                # [::step]
                start = 0
                stop  = len(self)
            elif start == None and stop == None and step < 0:
                # [::-step]
                start = len(self) - 1
                stop  = -1 # range limit needs to be past 0
            elif start != None and stop == None and step > 0:
                # [start::step]
                start = self._EnsureItsAnIndex(start)
                stop  = len(self)
            elif start != None and stop == None and step == None:
                # [start::]
                start = self._EnsureItsAnIndex(start)
                stop  = len(self)
                step  = 1
            elif start != None and stop == None and step < 0:
                # [start::-step]
                start = self._EnsureItsAnIndex(start)
                stop  = -1
            elif start == None and stop != None and step > 0:
                # [:stop:step]
                start = 0
                stop  = self._EnsureItsAnIndex(stop)
            elif start == None and stop != None and step == None:
                # [:stop]
                start = 0
                stop  = self._EnsureItsAnIndex(stop)
                step  = 1
            elif start == None and stop != None and step < 0:
                # [:stop:-step]
                start = 0
                stop  = self._EnsureItsAnIndex(stop)
            index = slice(start,stop,step)
            #construct and return a new instance of the class
            a = Tfs()
            a._CopyMetaData(self)

            # whether to prepare new s coordinates as extra entry
            prepareNewS = False
            sOffset     = 0
            if start > 0 and 'S' in self.columns:
                prepareNewS = True
                # note S is at the end of an element, so take the element before for offset ( start - 1 )
                # if 'S' is in the columns, 'SORIGINAL' will be too
                sOffset = self.GetRowDict(self.sequence[start-1])['SORIGINAL']
                sOffsetMid = self.GetRowDict(self.sequence[start-1])['SMID']
            # prepare S coordinate and append to each list per element
            for i in range(index.start,index.stop,index.step):
                elementlist = list(self.data[self.sequence[i]]) # copy instead of modify existing
                if prepareNewS:
                    # maintain the original s from the original data
                    elementlist[self.ColumnIndex('S')] = elementlist[self.ColumnIndex('SORIGINAL')] - sOffset
                    elementlist[self.ColumnIndex('SMID')] = elementlist[self.ColumnIndex('SMID')] - sOffsetMid
                a._AppendDataEntry(self.sequence[i], elementlist)

            a.smax = max(a.GetColumn('S'))
            a.smin = min(a.GetColumn('S'))
            return a
        
        elif type(index) == int or type(index) == _np.int64:
            return self.GetRowDict(self.sequence[index])
        elif type(index) == str:
            return self.GetRowDict(index)
        else:
            raise ValueError("argument not an index or a slice")
    
    def _CheckName(self,name):
        if self.data.has_key(name):
            #name already exists - boo degenerate names!
            i = 1
            basename = name
            while self.data.has_key(name):
                name = basename+'_'+str(i)
                i = i + 1
            return name
        else:
            return name

    def _CopyMetaData(self,instance):
        params = ["header","columns","formats","filename"]
        for param in params:
            setattr(self,param,getattr(instance,param))
        #calculate the maximum s position - could be different based on the slice
        if 'S' in instance.columns:
            self.smax = instance[-1]['S']
        else:
            self.smax = 0

    def _DeepCopy(self,instance):
        #return type(self)(deepcopy(instance))
        self._CopyMetaData(instance)
        params = ["index","data","sequence","nitems","nsegments"]
        for param in params:
            setattr(self,param,_copy.deepcopy(getattr(instance,param)))

    def _AppendDataEntry(self,name,entry):
        if len(self.index) > 0:                   #check if there's any elements yet
            self.index.append(self.index[-1] + 1) #create an index
        else:
            self.index.append(0)
        self.sequence.append(name)  #append name to sequence
        self.nitems    += 1         #increment nitems
        self.data[name] = entry     #put the data in

    def __iadd__(self, other):
        self._CopyMetaData(other) #fill in any data from other instance
        for i in range(len(other)):
            key = other.sequence[i]
            self._AppendDataEntry(key,other.data[key])
        return self
            
    def NameFromIndex(self,index):
        """
        NameFromIndex(integerindex)

        return the name of the beamline element at index
        """
        return self.sequence[index]

    def NameFromNearestS(self,S):
        """
        NameFromNearestS(S) 

        return the name of the beamline element clostest to S 
        """
        
        i = self.IndexFromNearestS(S) 
        return self.sequence[i]

    def IndexFromNearestS(self, S):
        """
        IndexFromNearestS(S)

        return the index of the beamline element closest to S.

        """

        sd = self.GetColumn('S')
        if S > sd[-1]:
            # allow some margin in case point is only just beyond beam line.
            if S > sd[-1]+10:
                raise Exception("S outside of range") # >10m past beam line - too far
            else:
                print "Warning S",S,"greater than length of beam line",sd[-1]
                return -1 #index to last element
        else:
            result = _np.argmin(abs(sd - S))
            return result
        
    def _EnsureItsAnIndex(self, value):
        if type(value) == str:
            return self.IndexFromName(value)
        else:
            return value

    def IndexFromName(self,namestring):
        """
        Return the index of the element named namestring

        """
        return self.sequence.index(namestring)

    def ColumnIndex(self,columnstring):
        """
        Return the index to the column matching the name
        
        REMEMBER: excludes the first column NAME
        0 counting

        """
        return self.columns.index(columnstring)

    def GetColumn(self,columnstring):
        """
        Return a numpy array of the values in columnstring in order
        as they appear in the beamline
        """
        i = self.ColumnIndex(columnstring)
        return _np.array([self.data[name][i] for name in self.sequence])

    def GetColumnDict(self,columnstring):
        """
        GetColumnDict(columnstring)
        return all data from one column in a dictionary

        note not in order
        """
        i = self.ColumnIndex(columnstring)
        d = dict((k,v[i]) for (k,v) in self.data.iteritems())
        #note we construct the dictionary comprehension in a weird way
        #here because SL6 uses python2.6 which doesn't have dict comprehension
        return d

    def GetRow(self,elementname):
        """
        Return all data from one row as a list
        """
        try:
            d = self[elementname]
        except KeyError:
            print 'No such item',elementname,' in this tfs file'
            return None
        return [d[key] for key in self.columns]
    
    def GetRowDict(self,elementname):
        """
        Return a dictionary of all parameters for a specifc element
        given by element name.

        note not in order
        """
        #no dictionary comprehension in python2.6 on SL6
        d = dict(zip(self.columns,self.data[elementname]))
        return d

    def GetSegment(self,segmentnumber):
        a = Tfs()
        a._CopyMetaData(self)
        segmentindex = self.columns.index('SEGMENT')
        hasname = 'NAME' in self.columns
        for key in self.sequence:
            if self.data[key][segmentindex] == segmentnumber:
                a._AppendDataEntry(key,self.data[key])
        return a

    def EditComponent(self, index, variable, value):
        '''
        Edits variable of component at index and sets it to value.  Can
        only take indices as every single element in the sequence has
        a unique definition, and components which may appear
        degenerate/reused are in fact not in this data model.
        '''
        variableIndex = self.columns.index(variable)
        componentName = self.sequence[index]
        self.data[componentName][variableIndex] = value

    def InterrogateItem(self,itemname):
        """
        InterrogateItem(itemname)
        
        Print out all the parameters and their names for a 
        particlular element in the sequence identified by name.
        """
        for i,parameter in enumerate(self.columns):
            print parameter.ljust(10,'.'),self.data[itemname][i]

    def GetElementNamesOfType(self,typename):
        """
        GetElementNamesOfType(typename) 
        
        Returns a list of the names of elements of a certain type. Typename can 
        be a single string or a tuple or list of strings.

        Examples:
        
        >>> GetElementsOfType('SBEND')
        >>> GetElementsOfType(['SBEND','RBEND'])
        >>> GetElementsOfType(('SBEND','RBEND','QUADRUPOLE'))

        """
        if 'KEYWORD' in self.columns:
            i = self.ColumnIndex('KEYWORD')
        elif 'APERTYPE' in self.columns:
            i = self.ColumnIndex('APERTYPE')
        else:
            i = 0
        return [name for name in self.sequence if self.data[name][i] in typename]

    def GetElementsOfType(self,typename):
        """
        Returns a Tfs instance containing only the elements of a certain type.
        Typename can be a sintlge string or a tuple or list of strings.

        This returns a Tfs instance with all the same capabilities as this one.
        """
        names = self.GetElementNamesOfType(typename)
        a = Tfs()
        a._CopyMetaData(self)
        for key in names:
            a._AppendDataEntry(key,self.data[key])
        return a

    def ReportPopulations(self):
        """
        Print out all the population of each type of
        element in the beam line (sequence)
        """
        print 'Filename >',self.filename
        print 'Total number of items >',self.nitems
        if 'KEYWORD' in self.columns:
            i = self.ColumnIndex('KEYWORD')
        elif 'APERTYPE' in self.columns:
            i = self.ColumnIndex('APERTYPE')
        else:
            raise KeyError("No keyword or apertype columns in this Tfs file")
        
        keys = set([self.data[name][i] for name in self.sequence])
        populations = [(len(self.GetElementsOfType(key)),key) for key in keys]
        print 'Type'.ljust(15,'.'),'Population'
        for item in sorted(populations)[::-1]:
            print item[1].ljust(15,'.'),item[0]

    def Plot(self,filename='optics.pdf'):
        _PlotTfsBeta(self,outputfilename=filename)

    def PlotSimple(self,filename='optics.pdf'):
        _PlotTfsBeta(self,outputfilename=filename,machine=False)

    def IndexFromGmadName(self, gmadname, verbose=False):
        '''
        Returns the indices of elements which match the supplied gmad name.
        Useful because tfs2gmad strips punctuation from the component names, and irritating otherwise to work back.
        When multiple elements of the name match, returns the indices of all the components in a list.
        Arguments:
        gmadname     :    The gmad name of a component to search for.
        verbose      :    prints out matching name indices and S locations.  Useful for discriminating between identical names.
        '''
        indices = []
        #Because underscores are allowed in gmad names:
        punctuation = _string.punctuation.replace('_', '')
        for index, element in enumerate(self):
            #translate nothing to nothing and delete all forbidden chars from name.
            name = element['NAME']
            strippedName = name.translate(_string.maketrans("",""), punctuation)
            if _re.match(gmadname + "_?[0-9]*", strippedName):
                indices.append(index)
        if verbose:
            for index in indices:
                sPos = self.data[self.NameFromIndex(index)][self.ColumnIndex('S')]
                print " matches at S =", sPos, "@index", index
        if len(indices) == 1:
            return indices[0]
        elif len(indices) > 1:
            return indices
        else:
            raise ValueError(gmadname + ' not found in list')

    def ExpandThinMagnets(self):
        '''
        expand hkickers and vkickers.  not particularly useful or dynamic,
        but does work for expanding thin h/vkickers
        so long as they are adjacent to either a thick kicker or a drift.
        Not bothered to make robust as once the arbitrary thin multipole
        is introduced in BDSIM this will likely be redundant anyway.
        '''

        def FindFirstThickElement(startindex, direction):
            if direction == '+':
                indicex = range(startindex, len(self) + 1)
            elif direction == '-':
                indices = range(startindex, -1, -1)
            for index in indices:
                if self[index]['L'] > 0:
                    return index

        def InsertThickenedKicker(ele, kicker, thickness=0.002):

            if (ele['KEYWORD'] != 'DRIFT' and
                ele['KEYWORD'] != 'HKICKER' and
                ele['KEYWORD'] != 'VKICKER'):
                raise KeyError("""Can currently only insert thick elements
                by reducing either a drift or another kicker""")

            # the logic in this function is to try and stick a kicker
            # into the nearest thick element.  This is assumed to be
            # either a kicker or a drift.  This makes it easier as
            # no integrated strengths need to be adjusted when shortening
            # a component to make room for thickening a kicker.
            # From experience HKICKERs and VKICKERs seem to be often
            # grouped together in pairs, so it's good to be able to handle
            # adding a thick kicker to an already thick kicker.  Since hte length
            # isn't of much importance (except for sync rad), make room for a 2mm
            # kicker by default.  If then there is another kicker to be added,
            # eat into that thick kicker by 1mm.  This means that a max of
            # 2 kickers in a row can be successfully added to the end of
            # a drift, so long as it's sufficiently thick (i.e >= 2.0 mm).
            # this is assume to be the case a priori.  For this reason this
            # is not a very robust piece of code, to put it mildly, but useful
            # for my ends at this point in time.


            # data is stored in raw lists so get the right index for L and LRAD
            lengthInd = (self.columns).index('L')
            lradInd   = (self.columns).index('LRAD')
            smidInd   = (self.columns).index('SMID')
            sInd      = (self.columns).index('S')
            # get the data for the element to be eaten from and the kicker
            elementData = self.data[ele['NAME']]
            kickerData = self.data[kicker['NAME']]

            if ele['KEYWORD'] == 'DRIFT':
                # take 2 mm from drift and add 2 to kicker
                elementData[lengthInd] -= thickness
                kickerData[lengthInd] += thickness
                # zeroing lrad for clarity, but note that this is an imperfect conv
                # and synchrotron radiation will differ between two models.
                kickerData[lradInd] = 0

                kickerData[smidInd] -= thickness/2
                elementData[smidInd] -= thickness/2

                elementData[sInd] -= thickness

            # if thick element is a kicker, i.e already been converted
            # from previous step.
            else:
                  elementData[lengthInd] -= thickness/2
                  kickerData[lengthInd] += thickness/2
                  # zeroing lrad for clarity, but note that this is an imperfect conv
                  # and synchrotron radiation will differ between two models.
                  kickerData[lradInd] = 0.0

                  kickerData[smidInd] -= thickness/4
                  elementData[smidInd] -= thickness/4

                  elementData[sInd] -= thickness/2

        # get all thin magnets:
        thinmags = {}
        for index, element in enumerate(self):
            name = element['NAME']
            if (element['L'] == 0 and
                self.ComponentPerturbs(index,terse=True)):
                thinmags[name] = element

        # loop over magnets and find a nearby drift > 2mm
        for name, mag in thinmags.iteritems():

            #get thick elements before and after current one.
            kickInd   = self.IndexFromName(name)
            thinKicker = self[kickInd]
            thickInd  =  FindFirstThickElement(kickInd, '-')
            thickEle  = self[thickInd]

            if not (thickEle['KEYWORD'] == 'DRIFT' or
                    thickEle['KEYWORD'] == 'VKICKER' or
                    thickEle['KEYWORD'] == 'HKICKER'):
                thickInd = FindFirstThickElement(startInd, '+')
                thickEle = self[thickInd]

            if (thickEle['KEYWORD'] == 'DRIFT' and thickEle['L'] > 0.002):
                InsertThickenedKicker(thickEle, thinKicker)
            elif ((thickEle['KEYWORD'] == 'VKICKER' or
                   thickEle['KEYWORD'] == 'HKICKER') and
                  thickEle['L'] > 0.01):
                InsertThickenedKicker(thickEle, thinKicker)

    def ComponentPerturbs(self, indexInSequence, terse=True):
        '''
        Returns names of variables which would perturb a particle.
        Some components written out in TFS are redundant,
        so it's useful to know which components perturb a particle's motion.
        This is likely not an exhaustive check so refer to source if unsure.

        Checks integrated stengths (but not if L=0), HKICK and VKICK

        indexInSequence - index of component to be checked.
        terse           - print out the parameters which perturb if False
        '''
        
        return self.ElementPerturbs(self[index], terse)

    def ElementPerturbs(self, component, terse=True):
        """
        Search an invidivual dictionary representing a row in the TFS file
        for as to whether it perturbs.
        """

        perturbingParameters = []  # list of perturbing params which are abs>0

        # these checks may be incomplete..  just the ones i know of.

        # check the kls..  if length is zero then kls don't matter.
        if component['L'] > 0:
           for variable in component.keys():
               kls = _re.compile(r'K[0-9]*S?L') # matches all integrated strengths.
               if (_re.match(kls, variable) and
                   abs(component[variable]) > 0):
                   perturbingParameters.append(variable)

        #check the kick angles.
        if abs(component['VKICK']) > 0:
            perturbingParameters.append('VKICK')
        if abs(component['HKICK']) > 0:
            perturbingParameters.append('HKICK')

        if terse == False:
            if perturbingParameters:
                print "--Element: " + componentName + " @ index " + str(componentIndex) + " parameters:"
                for variable in perturbingParameters:
                    print variable + "= ", component[variable]
                    print "Length = ", component['L']

        if (not perturbingParameters):
            return False
        else:
            return perturbingParameters

    def SplitElement(self, SSplit):
        '''Splits the element found at SSplit given, performs the necessary
        operations on the lattice to leave the model functionally
        identical and returns the indices of the first and second
        component.  Element new name will be the same as the original
        except appended with a number corresponding to its location in
        the list of previously identically defined components used in
        the sequence and either "split_1" or "split_2" depending on
        which side of the split it is located.  It is necessary to
        append both of these numbers to ensure robust name mangling.

        WARNING: DO NOT SPLIT THE ELEMENT WHICH MARKS THE BEGINNING OF
        YOUR LATTICE.  YOUR OPTICS WILL BE WRONG!

        '''

        # the element to be split:
        originalIndex = self.IndexFromNearestS(SSplit)
        originalName = self.sequence[originalIndex]
        originalLength = self[originalName]['L']
        originalS = self[originalName]['S']
        elementType = self[originalName]['KEYWORD']

        # First of the two elements that the original is split into.
        # Remembering that in MADX S is at the end of the component.
        firstS = SSplit
        firstLength = originalLength - (originalS - SSplit)
        firstName = originalName + str("_split_1")
        firstIndex = originalIndex

        # second of two elements that original is split into:
        secondS = originalS
        secondLength = originalS - SSplit
        secondName = originalName + str("_split_2")
        secondIndex = originalIndex + 1

        # Get the parameters which affect the particle's motion
        perturbingParameters = self.ComponentPerturbs(originalIndex)

        # update the sequence
        self.sequence[originalIndex] = firstName
        self.sequence.insert(originalIndex, secondName)

        # Making data entries for new components
        self.data[firstName] = _copy.deepcopy(self.data[originalName])
        self.data[secondName] = _copy.deepcopy(self.data[originalName])
        del self.data[originalName]

        # Apply the relevant edits to the newly split component.
        self.EditComponent(firstIndex, 'L', firstLength)
        self.EditComponent(firstIndex, 'S', firstS)
        self.EditComponent(firstIndex, 'SMID', firstS - firstLength/2.0)
        self.EditComponent(firstIndex, 'SORIGINAL', originalS)
        self.EditComponent(firstIndex, 'NAME', firstName)

        self.EditComponent(secondIndex, 'L', secondLength)
        self.EditComponent(secondIndex, 'S', secondS)
        self.EditComponent(secondIndex, 'SMID', secondS - secondLength/2.0)
        self.EditComponent(secondIndex, 'SORIGINAL', originalS)
        self.EditComponent(secondIndex, 'NAME', secondName)
        # Assign the appropriate amount of kick to each of the two components
        ratio = firstLength/originalLength
        originalHKick = self[firstIndex]['HKICK']
        originalVKick = self[firstIndex]['VKICK']
        self.EditComponent(firstIndex, 'HKICK', ratio * originalHKick)
        self.EditComponent(firstIndex, 'VKICK', ratio * originalVKick)
        self.EditComponent(secondIndex, 'HKICK', ratio * originalHKick)
        self.EditComponent(secondIndex, 'VKICK', ratio * originalVKick)

        return firstIndex, secondIndex

    def WrapAroundElement(self, index):
        '''
        Define new starting point for lattice.  Element at index
        will become the new beginning of the lattice, and elements
        that came before the new start are appended to the end.
        Changes S and SMID appropriately.
        '''

        # Get the element which will be the new start's S and SMID
        # values.  These will be used for updating all the other
        # element's S and SMID.
        newStartS = self[index]['S']
        newStartSMid = self[index]['SMID']
        # Have to change SORIGINAL otherwise slicing won't work:
        newStartSOriginal = self[index]['SORIGINAL']
        # Getting the sequences for the new first and second
        # parts.
        newStart = self.sequence[index:]
        newEnd = self.sequence[:index]

        smax = self.smax
        for i in range(index, len(self)):
            elementS = self[i]['S']
            elementSMid = self[i]['SMID']
            elementSOriginal = self[i]['SORIGINAL']
            self.EditComponent(i, 'S', elementS - newStartS)
            self.EditComponent(i, 'SMID', elementSMid - newStartSMid)
            self.EditComponent(i, 'SORIGINAL', elementSOriginal - newStartSOriginal)
        for i in range(index):
            elementS = self[i]['S']
            elementSMid = self[i]['SMID']
            elementSOriginal = self[i]['SORIGINAL']
            self.EditComponent(i, 'S', elementS + (smax - newStartS))
            self.EditComponent(i, 'SMID', elementSMid + (smax - newStartSMid))
            self.EditComponent(i, 'SORIGINAL', elementSOriginal +
                               (smax - newStartSOriginal))

        self.sequence = self.sequence[index:] + self.sequence[:index]
        self.sequence = self.sequence[0:-1]


def CheckItsTfs(tfsfile):
    """
    Ensure the provided file is a Tfs instance.  If it's a string, ie path to
    a tfs file, open it and return the Tfs instance.
    
    tfsfile can be either a tfs instance or a string.
    """
    if type(tfsfile) == str:
        madx = pymadx.Tfs(tfsfile)
    elif type(tfsfile) == pymadx.Tfs:
        madx = tfsfile
    else:
        raise IOError("Not pymadx.Tfs file type: "+str(tfsfile))
    return madx