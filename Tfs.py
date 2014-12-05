import tarfile

class Tfs:
    """
    MADX Tfs file reader

    a = Tfs()
    a.Load('myfile.tfs')
    a.Load('myfile.tar') -> extracts from tar file

    a has data members:
    
    header  - dictionary of header items
    columns - list of column names
    formats - list of format strings for each column
    data    - dictionary of entries in tfs file by name string

    NOTE: this assumes NAME is the first column

    databyindex - dictionary by integer index in sequence
    sequence    - list of names in the order they appear in the file
    nitems      - number of items in sequence

    Examples:

    a.data['IP.1'] #returns all entries (minus the name) for element IP.1
    a.databyindex[321] #returns item number 321 from beamline (0 counting)

    """
    def __init__(self,filename=None):
        self.index       = []
        self.header      = {}
        self.columns     = []
        self.formats     = []
        self.data        = {}
        self.databyindex = {}
        self.sequence    = []
        self.nitems      = 0
        self.filename    = filename
        if filename != None:
            self.Load(filename)
        
    def Clear(self):
        self.__init__()
    
    def Load(self,filename):
        """
        Load('filename.tfs')
        
        read the tfs file and prepare data structures
        """
        if filename.endswith('tar'):
            #it's gzipped - extract to temporary file
            print 'zipped file'
            tar = tarfile.open(filename,'r:gz')
            f = tar.extractfile(tar.firstmember)
        else:
            #normal file
            print 'normal file'
            f = open(filename)

        for line in f:
            splitline = line.strip('\n').split()
            sl        = splitline #shortcut
            if line[0] == '@':
                #header
                self.header[sl[1]] = sl[-1].replace('"','')
            elif line[0] == '*':
                #name
                self.columns.extend(sl[2:]) #miss * and NAMES
            elif line[0] == '$':
                #format
                self.formats.extend(sl[2:]) #miss $ and NAMES
            else:
                #data
                d = [Cast(item) for item in sl]
                name = self._CheckName(d[0])
                self.sequence.append(name) # keep the name in sequence
                self.data[name] = d[1:]    # put in data dict by name
                self.databyindex[self.nitems] = d
                self.nitems += 1 # keep tally of number of items
        f.close()

        self.index = range(0,len(self.data),1)

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

    def NameFromIndex(self,index):
        """
        NameFromIndex(integerindex)

        return the name of the beamline element at index
        """
        return self.sequence[index]

    def NameFromNearestS(self,S) : 
        """
        NameFromNearestS(S) 

        return the name of the beamline element clostest to S 
        """
        
        i = self.IndexFromNearestS(S) 
        return self.sequence[i]

    def IndexFromNearestS(self,S) : 
        """
        IndexFromNearestS(S) 

        return the index of the beamline element clostest to S 
        """
        s = self.ColumnByIndex('S')

        ci = [i for i in self.index[0:-1] if (S > s[i]  and S < s[i+1])] 
        ci = ci[0]

        if abs(S-s[ci]) < abs(S-s[ci+1]) : 
            return ci 
        else : 
            return ci+1 



    def IndexFromName(self,namestring):
        """
        IndexFromName(namestring)

        return the index of the element named namestring

        """
        return self.sequence.index(namestring)

    def ColumnIndex(self,columnstring):
        """
        ColumnIndex(columnname):
        
        return the index to the column matching the name
        
        REMEMBER: excludes the first column NAME
        0 counting

        """
        return self.columns.index(columnstring)

    def ColumnByName(self,columnstring):
        """
        Column(columnstring)
        return all data from one column

        returns a dictionary by name of item
        """
        i = self.ColumnIndex(columnstring)
        d = {k:v[i] for (k,v) in self.data.iteritems()}
        return d

    def ColumnByIndex(self,columnstring):
        """
        ColumnByIndex(columnstring)
        
        returns a list of the values in columnstring in order
        as they appear in the beamline

        """
        i = self.ColumnIndex(columnstring)
        return [self.data[name][i] for name in self.sequence]

    def InterrogateItem(self,itemname):
        """
        InterrogateItem(itemname)
        
        Print out all the parameters and their
        names for a particlular element in the 
        sequence identified by name
        """
        for i,parameter in enumerate(self.columns):
            print parameter.ljust(10,'.'),self.data[itemname][i]

    def GetElementsOfType(self,typename):
        """
        GetElementsOfType(typename) ie GetElementsOfType('SBEND')

        Returns a list of the names of elements of a certain type
        """        
        i = self.ColumnIndex('KEYWORD')
        return [name for name in self.sequence if self.data[name][i] == typename]

    def GetElementsOfTypes(self,typenames) :
        """
        GetElementsOfTypes(typenames) ie GetElementsOfType(['SBEND','RBEND'])

        Returns a list of the names of elements of a certain type
        """        
        i = self.ColumnIndex('KEYWORD')
        return [name for name in self.sequence if self.data[name][i] in typenames ]

    def ReportPopulations(self):
        """
        Print out all the population of each type of
        element in the beam line (sequence)
        """
        print 'Filename > ',self.filename
        print 'Total number of items > ',self.nitems
        i = self.ColumnIndex('KEYWORD')
        keys = set([self.data[name][i] for name in self.sequence])
        populations = [(len(self.GetElementsOfType(key)),key) for key in keys]
        print 'Type'.ljust(15,'.'),'Population'
        for item in sorted(populations)[::-1]:
            print item[1].ljust(15,'.'),item[0]
        


def Cast(string):
    """
    Cast(string)
    
    tries to cast to a (python)float and if it doesn't work, 
    returns a string

    """
    try:
        return float(string)
    except ValueError:
        return string.replace('"','')