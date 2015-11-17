from pymadx import Tfs as _Tfs
from bisect import bisect as _bisect
import numpy as _np


class Aperture(_Tfs):
    """
    A class based on (which inherits) the Tfs class for reading aperture information.
    This allows madx aperture information in Tfs format to be loaded, filtered and 
    queried. This also provides the ability to suggest whether an element should be
    split and therefore what the aperture should be.

    This class maintains a cache of aperture information as a function of S position.

    """
    def __init__(self, *args, **kwargs):
        _Tfs.__init__(self, *args, **kwargs)
        if 'debug' in kwargs:
            self.debug = kwargs['debug']
        else:
            self.debug = False
        # the tolerance below which, the aperture is considered 0
        self._tolerance = 1e-6
        self._UpdateCache()
        
    def _UpdateCache(self):
        # create a cache of which aperture is at which s position
        # do this by creatig a map of the s position of each entry
        # with the associated 
        self.cache = {}

        print('Aperture> preparing cache')
        for item in self:
            s = item['S']
            if s in self.cache.keys():
                #if existing one is zero and other isn't replace it
                if ZeroAperture(self.cache[s]) and NonZeroAperture(item):
                    self.cache[s] = item
            else:
                self.cache[s] = item

        # dictionary is not ordered to keep list of ordered s positions
        self._ssorted = self.cache.keys()
        self._ssorted.sort()

        # pull out some aperture values for conevience
        # try this as class may be constructed with no data
        try:
            for key in ['APER_1', 'APER_2', 'APER_3', 'APER_4']:
                setattr(self, '_'+str.lower(key), self.GetColumn(key))
        except ValueError:
            pass

    def SetZeroTolerance(self, tolerance):
        """
        Set the value below which aperture values are considered 0.
        """
        self._tolerance = tolerance

    def GetNonZeroItems(self):
        """
        Return a copy of this class with all non-zero items removed.

        """
        print 'Aperture> removing zero aperture items'
        # prepare list of relevant aperture keys to check
        aperkeys = []
        aperkeystocheck = ['APER_%s' %n for n in [1,2,3,4]]
        for key in aperkeystocheck:
            if key in self.columns:
                aperkeys.append(key)
            else:
                print key,' will be ignored as not in this aperture Tfs file'
        if len(aperkeys) == 0:
            raise KeyError("This file does not contain APER_1,2,3 or 4 - required!")

        # prepare resultant tfs instance
        a = Aperture()
        a._CopyMetaData(self)
        for item in self:
            apervalues = _np.array([item[key] for key in aperkeys])
            nonzeros = apervalues > self._tolerance
            nonzero  = nonzeros.any() #if any are true
            if nonzero:
                if item['APER_1'] < self._tolerance:
                    continue # aper1 must at least be non zero
                key = self.sequence[self._iterindex]
                a._AppendDataEntry(key, self.data[key])
        a._UpdateCache()
        return a

    def GetEntriesBelow(self, value=8, keys='all'):
        return self.RemoveAboveValue(value,keys)
    
    def RemoveAboveValue(self, limits=8, keys='all'):
        print 'Aperture> removing any aperture entries above',limits
        if keys == 'all':
            aperkeystocheck = ['APER_%s' %n for n in [1,2,3,4]]
        elif type(keys) in (float, int):
            aperkeystocheck = [keys]
        elif type(keys) in (list, tuple):
            aperkeystocheck = list(keys)

        limitvals = _np.array(limits) # works for single value, list or tuple in comparison

        # check validity of the supplied keys
        aperkeys = []
        for key in aperkeystocheck:
            if key in self.columns:
                aperkeys.append(key)
            else:
                print key,' will be ignored as not in this aperture Tfs file'

        a = Aperture()
        a._CopyMetaData(self)
        for item in self:
            apervals = _np.array([item[key] for key in aperkeys])
            abovelimit = apervals > limitvals
            abovelimittotal = abovelimit.any() # if any are true
            if not abovelimittotal:
                key = self.sequence[self._iterindex]
                a._AppendDataEntry(key, self.data[key])
        a._UpdateCache()
        return a

    def GetUniqueSPositions(self):
        return self.RemoveDuplicateSPositions()

    def RemoveDuplicateSPositions(self):
        """
        Takes the first aperture value for entries with degenerate S positions and
        removes the others.
        """
        print 'Aperture> removing entries with duplicate S positions'
        # check if required at all
        if len(self) == len(self._ssorted):
            # no duplicates!
            return self
        
        a = Aperture()
        a._CopyMetaData(self)
        u,indices = _np.unique(self.GetColumn('S'), return_index=True)
        for ind in indices:
            key = self.sequence[ind]
            a._AppendDataEntry(key, self.data[key])
        a._UpdateCache()
        return a

    def _GetIndexInCacheOfS(self, sposition):
        index = _bisect(self._ssorted, sposition)
        if index > 0:
            return index - 1
        else:
            return index

    def GetApertureAtS(self, sposition):
        """
        Return a dictionary of the aperture information specified at the closest
        S position to that requested - may be before or after that point.
        """
        return self[self._GetIndexInCacheOfS(sposition)]
        
    def GetApertureForElementNamed(self, name):
        """
        Return a dictionary of the aperture information by the name of the element.
        """
        return self.GetRow(name)

    def GetRow(self, key):
        """
        Get a single entry / row in the Tfs file as a list.
        """
        try:
            _Tfs.GetRow(self,key)
        except KeyError:
            print 'No such key',key,' in this aperture file'
            return None

    def ReplaceType(self, existingType, replacementType):
        print 'Aperture> replacing',existingType,'with',replacementType
        et = existingType    #shortcut
        rt = replacementType #shortcut
        try:
            index = self.columns.index('APERTYPE')
        except ValueError:
            print 'No apertype column, therefore no type to replace'
            return
        for item in self:
            try:
                if item['APERTYPE'] == et:
                    self.data[item['NAME']][index] = rt
            except KeyError:
                return

    def ShouldSplit(self, rowDictionary):
        """
        Suggest whether a given element should be split as the aperture information
        in this class suggests multiple aperture changes within the element.

        Returns bool, [], []
        
        which are in order:

        bool - whether to split or not
        []   - list of lengths of each suggested split
        []   - list of the aperture dictionaries for each one

        """
        l      = rowDictionary['L']
        sEnd   = rowDictionary['S']
        sStart = sEnd -l
        
        indexStart = self._GetIndexInCacheOfS(sStart)
        indexEnd   = self._GetIndexInCacheOfS(sEnd)
        # get the s positions of any defined aperture points within
        # the length of the element
        apertureSValuesInRange = self._ssorted[indexStart:indexEnd]

        # calculate differentials of aperture values in range of the element
        # test if any are non-zero
        bdA1 = _np.diff(self._aper_1[indexStart:indexEnd]) != 0
        bdA2 = _np.diff(self._aper_2[indexStart:indexEnd]) != 0
        bdA3 = _np.diff(self._aper_3[indexStart:indexEnd]) != 0
        bdA4 = _np.diff(self._aper_4[indexStart:indexEnd]) != 0
        
        # find if there are any changes in aperture for any parameter
        shouldSplit = _np.array([bdA1, bdA2, bdA3, bdA4]).any()

        if self.debug:
            print 'length: ',l,', S (start): ',sStart,', S (end): ',sEnd
            print 'Index (start): ',indexStart,', Index(end): ',indexEnd
            print 'Any difference in aper1: ',bdA1
            print 'Any difference in aper2: ',bdA2
            print 'Any difference in aper3: ',bdA3
            print 'Any difference in aper4: ',bdA4

        if not shouldSplit:
            # return false and the aperture model to be use for the whole item
            sMid = (sEnd - sStart) / 2
            return False, [l], [self.GetApertureAtS(sMid)]
        else:
            if self.debug:
                print 'Recommend splitting element'
            # should split!
            # work out s locations at split points
            
            # put all selection boolean arrays into one large 2D array
            # of nonzero differential vs aperture parameter
            bdA = _np.array([bdA1, bdA2, bdA3, bdA4])
            # get the a unique set of the indices where any aperture changes
            # nonzero->bool array, take only which items (rows) have nonzero diffs, take set of to remove duplication
            indices = _np.array(list(set(bdA.nonzero()[1]))) 
            indices += indexStart # add on offset to get index for whole data
            if self.debug:
                print indices
            sSplits = _np.array([self._ssorted[x] for x in indices]) # s positions of aperture changes
            if len(sSplits) > 1:
                while sSplits[0] < sStart:
                    sSplits = sSplits[1:] # remove any elements before the start position of this element
            sSplitStart = _np.array(sSplits) #copy the starts
            sSplitStart = _np.insert(sSplitStart, 0, sStart) # prepend s of first element
            # work out the length of each section
            lSplits = sSplits - sStart

            # replace any <0 lengths ie nearest aperture definition behind start of this object
            # ignore these and only take aperture definitions in front of the element
            lSplits = lSplits[lSplits > 0]
            
            if self.debug:
                print lSplits

            # lSplits is just the length of the proposed split points from the start
            # make them a local S within the element by prepending 0 and appending L(ength)
            lSplits = _np.insert(lSplits, 0, 0)
            lSplits = _np.append(lSplits, l) # make length last one
            
            if self.debug:
                print lSplits
            
            lSplits = _np.diff(lSplits)

            # paranoid checks - trim / adjust last element to conserve length accurately
            if lSplits.sum() != l:
                lSplits[-1] = lSplits[-1] + (l - lSplits.sum())

            # get the mid point of each split segment for asking what the aperture should be
            sSplitMid = sSplitStart + lSplits*0.5
            apertures = [self.GetApertureAtS(s) for s in sSplitMid]

            # check result of attempted splitting
            result = True if len(sSplits)>1 else False
            if len(apertures) > len(sSplits):
                apertures = apertures[:len(sSplits)] #should index 1 ahead - counteracts 0 counting
            
            return result, lSplits, apertures


def NonZeroAperture(item):
    tolerance = 1e-9
    test1 = item['APER_1'] > tolerance
    test2 = item['APER_2'] > tolerance
    test3 = item['APER_3'] > tolerance
    test4 = item['APER_4'] > tolerance

    return test1 or test2 or test3 or test4

def ZeroAperture(item):
    tolerance = 1e-9
    test1 = item['APER_1'] < tolerance
    test2 = item['APER_2'] < tolerance
    test3 = item['APER_3'] < tolerance
    test4 = item['APER_4'] < tolerance

    return test1 and test2 and test3 and test4
