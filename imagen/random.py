
"""
Two-dimensional pattern generators drawing from various random distributions.
"""
__version__='$Revision$'

import numpy as np

from numpy.oldnumeric import zeros,floor,where,choose,less,greater,Int,random_array

import param
from param.parameterized import ParamOverrides

from patterngenerator import PatternGenerator
from . import Composite, Gaussian
from sheetcoords import SheetCoordinateSystem



def seed(seed=None):
    """
    Set the seed on the shared RandomState instance.

    Convenience function: shortcut to RandomGenerator.random_generator.seed().
    """
    RandomGenerator.random_generator.seed(seed)


class RandomGenerator(PatternGenerator):
    """2D random noise pattern generator abstract class."""

    __abstract = True

    # The orientation is ignored, so we don't show it in
    # auto-generated lists of parameters (e.g. in the GUI)
    orientation = param.Number(precedence=-1)

    random_generator = param.Parameter(
        default=np.random.RandomState(seed=(500,500)),precedence=-1,doc=
        """
        numpy's RandomState provides methods for generating random
        numbers (see RandomState's help for more information).

        Note that all instances will share this RandomState object,
        and hence its state. To create a RandomGenerator that has its
        own state, set this parameter to a new RandomState instance.
        """)


    def _distrib(self,shape,p):
        """Method for subclasses to override with a particular random distribution."""
        raise NotImplementedError

    # Optimization: We use a simpler __call__ method here to skip the
    # coordinate transformations (which would have no effect anyway)
    def __call__(self,**params_to_override):
        p = ParamOverrides(self,params_to_override)

        shape = SheetCoordinateSystem(p.bounds,p.xdensity,p.ydensity).shape

        result = self._distrib(shape,p)
        self._apply_mask(p,result)

        for of in p.output_fns:
            of(result)

        return result


class DenseNoise(RandomGenerator):
    """
    2D Dense noise pattern generator with variable and free grid size
    
    By default this produces a matrix with random values 0.0, 0.5 and 1
    When a scale and an offset are provided the transformation maps them to:
     0 -> offset 
     0.5 -> offset + 0.5 * scale
     1 -> offset + scale 
     
    if grid_size > 1 then instead of entries spots or boxes with size equal
    to grid_size filled with 0, 0.5 or 1 will be mapped to the full matrix 
 
    ---
    Examples 
    ---
    DenseNoise(grid_density = 1, bounds = BoundingBox(radius = 1),
    xdensity = 4, ydensity = 4)  will produce something like this:
     
    [[ 0.  0.  0.  0.  1.  1.  1.  1.]
    [ 0.  0.  0.  0.  1.  1.  1.  1.]   Here there are two units per side and therefore
    [ 0.  0.  0.  0.  1.  1.  1.  1.]   grid_density = 1 indicates that the matrix
    [ 0.  0.  0.  0.  1.  1.  1.  1.]   will be divided in 2 * 2 boxes 
    [ 1.  1.  1.  1.  0.  0.  0.  0.]
    [ 1.  1.  1.  1.  0.  0.  0.  0.]
    [ 1.  1.  1.  1.  0.  0.  0.  0.]
    [ 1.  1.  1.  1.  0.  0.  0.  0.]]
    
    DenseNoise(grid_density = 2, bounds = BoundingBox(radius = 1),
    xdensity = 4, ydensity = 4) on the other hand will produce:
    
    [[ 1.   1.   0.   0.   0.   0.   0.5  0.5]
    [ 1.   1.   0.   0.   0.   0.   0.5  0.5] Here again there are two units per side and therefore
    [ 1.   1.   1.   1.   0.   0.   0.   0. ] grind_density = 2 indicates that 
    [ 1.   1.   1.   1.   0.   0.   0.   0. ] the matrix will be divided in 4 * 4 boxes 
    [ 0.   0.   0.5  0.5  1.   1.   1.   1. ]
    [ 0.   0.   0.5  0.5  1.   1.   1.   1. ]
    [ 1.   1.   0.   0.   1.   1.   1.   1. ]
    [ 1.   1.   0.   0.   1.   1.   1.   1. ]]
    
    ---
    Notes 
    ---
    1 ) This method works much faster when the noise matrix falls neatly
    into the pixel matrix ( ~ 100 times faster)
       
    2 ) In case that the a pixel has an intersection with two or more squares from the noise
    grid, the allocating of the value is done by taking into account where the center
    of the pixels lies
    
    3) If a particular number of cells N is wanted it is necessary to divide it by the length of 
    the side of the bounding box. 
    
    For example if the user wnats to have N = 10 cells and  the following bounding box is used 
    BoundingBox(radius = 1) the density must be set to N / 2 = 5 in order to have ten cells. 
    
    Note that the x-density and y-density must be both bigger than 5 in order for this work
    """
    
    grid_density = param.Number(default=1, bounds=(None,None), doc="""
    Grid elements per unit """)

    def _distrib(self, shape, p):               
        assert ( p.grid_density <= p.xdensity ), 'grid density bigger than pixel density x'
        assert ( p.grid_density <= p.ydensity),  'grid density bigger than pixel density y'
        assert ( shape[1] > 0 ), 'Pixel matrix can not be zero'
        assert ( shape[0] > 0 ),  'Pixel matrix can not be zero'
        
        Nx = shape[1]  
        Ny = shape[0] # Size of the pixel matrix 
      
        SC = SheetCoordinateSystem(p.bounds, p.xdensity, p.ydensity)
        unitary_distance_x = SC._SheetCoordinateSystem__xstep
        unitary_distance_y = SC._SheetCoordinateSystem__ystep

        
        sheet_x_size = unitary_distance_x * Nx 
        sheet_y_size = unitary_distance_y * Ny

        # Sizes of the structure matrix 
        nx = int(round(sheet_x_size * p.grid_density))  # Number of points in the x's
        ny = int(round(sheet_y_size * p.grid_density))  # Number of points in the y's
        
        assert ( nx > 0 ), 'Grid density or bound box in the x dimension too smal'
        assert ( ny > 0 ), 'Grid density or bound bonx in the y dimension too smal'
        
        # If the noise grid is proportional to the pixel grid 
        # and fits neatly into it then this method is faster (~100 times faster)
        if ( Nx % nx == 0) and (Ny % ny == 0):
              
            if (Nx == nx) and (Ny == ny):  #This is faster to call the whole procedure 
                result = 0.5 * (p.random_generator.randint(-1, 2, shape) + 1)
                return  result * p.scale + p.offset
            
            else: 
                # This is the actual matrix of the pixels 
                A = np.zeros(shape)    
                # Noise matrix that contains the structure of 0, 0.5 and 1's  
                Z = 0.5 * (p.random_generator.randint(-1, 2, (nx, ny)) + 1 )               

                ps_x = int(round(Nx * 1.0/ nx))  #Closest integer 
                ps_y = int(round(Ny * 1.0/ ny))
        
                # Noise matrix is mapped to the pixel matrix   
                for i in range(nx):
                    for j in range(ny): 
                        A[i * ps_y: (i + 1) * ps_y, j * ps_x: (j + 1) * ps_x] = Z[i,j]

                return A * p.scale + p.offset
            
        # General method in case the noise grid does not 
        # fall neatly in the pixels grid      
        else:
            
            # Obtain length of the side and length of the
            # division line between the grid 
            x_points,y_points = SC.sheetcoordinates_of_matrixidx()

            division_x = 1.0 / p.grid_density
            division_y = 1.0 / p.grid_density
            
            # This is the actual matrix of the pixels 
            A = np.zeros(shape)
            # Noise matrix that contains the structure of 0, 0.5 and 1's  
            Z = 0.5 * (p.random_generator.randint(-1, 2, (nx, ny)) + 1 )

            size_of_block_x = Nx * 1.0 / nx
            size_of_block_y = Ny * 1.0 / ny
            
            # Noise matrix is mapped to the pixel matrix   
            for i in range(Nx):
                for j in range(Ny):
                    # Map along the x coordinates 
                    x_entry = int( i / size_of_block_x)
                    y_entry = int( j / size_of_block_y)
                    A[j][i] = Z[x_entry][y_entry]
                
            return A * p.scale + p.offset

class SparseNoise(RandomGenerator):

    '''
    2D sparse noise pattern generator with variable and free grid size
    
    In the default this produces a matrix with 0.5 everywhere except in one 
    random entry. This value is randomly assigned to either  0 or 1 and then
    is scaled with the parameters scale and offset in the following way
    
     0 -> offset 
     1 -> offset + scale 
                  
    ---
    Example 
    ---
    
    SparseNoise(grid_density = 1, grid = True, bounds = BoundingBox(radius = 1),
    xdensity = 4, ydensity = 4) will produce something like this
   
    [[ 0.5  0.5  0.5  0.5  0.0  0.0  0.0  0.0]      Here there are two units per side, and therefore
     [ 0.5  0.5  0.5  0.5  0.0  0.0  0.0  0.0] < -- grid_density = 1 indicates that the 
     [ 0.5  0.5  0.5  0.5  0.0  0.0  0.0  0.0]      matrix will be divided in 2 * 2 boxes 
     [ 0.5  0.5  0.5  0.5  0 0  0.0  0.0  0.0]
     [ 0.5  0.5  0.5  0.5  0.5  0.5  0.5  0.5]
     [ 0.5  0.5  0.5  0.5  0.5  0.5  0.5  0.5]
     [ 0.5  0.5  0.5  0.5  0.5  0.5  0.5  0.5]
     [ 0.5  0.5  0.5  0.5  0.5  0.5  0.5  0.5]]    
     
    SparseNoise(grid_density = 2, grid = True, bounds = BoundingBox(radius = 1) ,
    xdensity = 4, ydensity = 4) on the other hand will produce:
     
   [[ 0.5  0.5  0.  0.  0.  0.  0.  0.]
    [ 0.5  0.5  0.  0.  0.  0.  0.  0.]
    [ 0.5  0.5  0.  0.  0.  0.  0.  0.]
    [ 0.5  0.5  0.  0.  0.  0.  0.  0.]       Here there are two units per side and therefore
    [ 0.5  0.5  0.  0.  0.  0.  1.  1.] < --- grid_density = 2 indicates that the 
    [ 0.5  0.5  0.  0.  0.  0.  1.  1.]       matrix will be divided in 4 * 4 boxes  
    [ 0.5  0.5  0.  0.  0.  0.  0.  0.]
    [ 0.5  0.5  0.  0.  0.  0.  0.  0.]]

    ---
    Notes 
    ---
    
    1 ) This method works much faster when the noise matrix falls neatly
    into the pixel matrix ( ~ 100 times faster)
       
    2 ) In case that the a pixel has an intersection with two or more squares from the noise
    grid, the allocating of the value is done by taking into account where the center
    of the pixels lies
    
    3) If a particular number of cells N is wanted it is necessary to divide it by the length of 
    the side of the bounding box. 
    
    For example if the user wnats to have N = 10 cells and  the following bounding box is used 
    BoundingBox(radius = 1) the density must be set to N / 2 = 5 in order to have ten cells. 
    
    Note that the x-density and y-density must be both bigger than 5 in order for this work
    
    '''
    
  
    grid_density = param.Number(default=1, bounds=(None,None), doc="""
    Grid elements per unit """)
   
    grid = param.Boolean(default = True, doc=""" 
    True - Forces the spots to appear in a grid
    False - The patterns can appear randomly anywhere d""")

    
    def _distrib(self, shape, p):
        assert ( p.grid_density <= p.xdensity ), 'grid density bigger than pixel density x'
        assert ( p.grid_density <= p.ydensity),  'grid density bigger than pixel density y'
        assert ( shape[1] > 0 ), 'Pixel matrix can not be zero'
        assert ( shape[0] > 0 ),  'Pixel matrix can not be zero'
        
        Nx = shape[1]  
        Ny = shape[0] # Size of the pixel matrix 
        
      
        SC = SheetCoordinateSystem(p.bounds, p.xdensity, p.ydensity)
        unitary_distance_x = SC._SheetCoordinateSystem__xstep
        unitary_distance_y = SC._SheetCoordinateSystem__ystep

        sheet_x_size = unitary_distance_x * Nx 
        sheet_y_size = unitary_distance_y * Ny

        # Sizes of the structure matrix 
        nx = int(round(sheet_x_size * p.grid_density))  # Number of points in the x's
        ny = int(round(sheet_y_size * p.grid_density))  # Number of points in the y's
        
        assert ( nx > 0 ), 'Grid density or bound box in the x dimension too smal'
        assert ( ny > 0 ), 'Grid density or bound bonx in the y dimension too smal'
        
        ps_x = int(round(Nx / nx)) #Closest integer 
        ps_y = int(round(Ny / ny))
              
        # This is the actual matrix of the pixels 
        A = np.ones(shape) * 0.5   
           
        if p.grid == False:  #The centers of the spots are randomly distributed in space 
                        
            x = p.random_generator.randint(0, Nx - ps_x + 1)
            y = p.random_generator.randint(0, Ny - ps_y + 1)
            z = p.random_generator.randint(0,2) 
                        
            # Noise matrix is mapped to the pixel matrix   
            A[x: (x + ps_y), y: (y + ps_x)] =  z   
           
            return A * p.scale + p.offset
        
        else: #In case you want the grid
            
            if  ( Nx % nx == 0) and (Ny % ny == 0): #When the noise grid falls neatly into the the pixel grid 
                x = p.random_generator.randint(0, nx)
                y = p.random_generator.randint(0, ny)
                z = p.random_generator.randint(0,2) 
                
               # Noise matrix is mapped to the pixel matrix (faster method)       
                A[x*ps_y: (x*ps_y + ps_y), y*ps_x: (y*ps_x + ps_x)] = z  
                
                return A * p.scale + p.offset
                    
            else: # If noise grid does not fit neatly in the pixel grid (slow method)
                
                x_points,y_points = SC.sheetcoordinates_of_matrixidx()
                
                # Obtain length of the side and length of the
                # division line between the grid 
                
                division_x = 1.0 / p.grid_density
                division_y = 1.0 / p.grid_density

                size_of_block_x = Nx * 1.0 / nx
                size_of_block_y = Ny * 1.0 / ny
            
                # Construct the noise matrix 
                Z = np.ones((nx,ny)) * 0.5
                x = p.random_generator.randint(0, nx)
                y = p.random_generator.randint(0, ny)
                z = p.random_generator.randint(0,2) 
                Z[x,y] = z
                
                            # Noise matrix is mapped to the pixel matrix   
                for i in range(Nx):
                    for j in range(Ny):
                        # Map along the x coordinates 
                        x_entry = int( i / size_of_block_x)
                        y_entry = int( j / size_of_block_y)
                        A[j][i] = Z[x_entry][y_entry]

                return A * p.scale + p.offset

         
class UniformRandom(RandomGenerator):
    """2D uniform random noise pattern generator."""

    def _distrib(self,shape,p):
        return p.random_generator.uniform(p.offset, p.offset+p.scale, shape)



class UniformRandomInt(RandomGenerator):
    """
    2D distribution of integer values from low to high in the in the
    half-open interval [`low`, `high`).

    Matches semantics of numpy.random.randint.
    """

    low = param.Integer(default=0, doc="""
        Lowest integer to be drawn from the distribution.""")

    high = param.Integer(default=2, doc="""
        The highest integer to be drawn from the distribution.""")

    def _distrib(self,shape,p):
        return np.random.randint(p.low, p.high, shape)



class BinaryUniformRandom(RandomGenerator):
    """
    2D binary uniform random noise pattern generator.

    Generates an array of random numbers that are 1.0 with the given
    on_probability, or else 0.0, then scales it and adds the offset as
    for other patterns.  For the default scale and offset, the result
    is a binary mask where some elements are on at random.
    """

    on_probability = param.Number(default=0.5,bounds=[0.0,1.0],doc="""
        Probability (in the range 0.0 to 1.0) that the binary value
        (before scaling) is on rather than off (1.0 rather than 0.0).""")

    def _distrib(self,shape,p):
        rmin = p.on_probability-0.5
        return p.offset+p.scale*(p.random_generator.uniform(rmin,rmin+1.0,shape).round())



class GaussianRandom(RandomGenerator):
    """
    2D Gaussian random noise pattern generator.

    Each pixel is chosen independently from a Gaussian distribution
    of zero mean and unit variance, then multiplied by the given
    scale and adjusted by the given offset.
    """

    scale  = param.Number(default=0.25,softbounds=(0.0,2.0))
    offset = param.Number(default=0.50,softbounds=(-2.0,2.0))

    def _distrib(self,shape,p):
        return p.offset+p.scale*p.random_generator.standard_normal(shape)


# CEBALERT: in e.g. script_repr, an instance of this class appears to
# have only pattern.Constant() in its list of generators, which might
# be confusing. The Constant pattern has no effect because the
# generators list is overridden in __call__. Shouldn't the generators
# parameter be hidden for this class (and possibly for others based on
# pattern.Composite)? For that to be safe, we'd at least have to have
# a warning if someone ever sets a hidden parameter, so that having it
# revert to the default value would always be ok.

class GaussianCloud(Composite):
    """Uniform random noise masked by a circular Gaussian."""

    operator = param.Parameter(np.multiply)

    gaussian_size = param.Number(default=1.0,doc="Size of the Gaussian pattern.")

    aspect_ratio  = param.Number(default=1.0,bounds=(0.0,None),softbounds=(0.0,2.0),
        precedence=0.31,doc="""
        Ratio of gaussian width to height; width is gaussian_size*aspect_ratio.""")

    def __call__(self,**params_to_override):
        p = ParamOverrides(self,params_to_override)
        p.generators=[Gaussian(aspect_ratio=p.aspect_ratio,size=p.gaussian_size),
                      UniformRandom()]
        return super(GaussianCloud,self).__call__(**p)



### JABHACKALERT: This code seems to work fine when the input regions
### are all the same size and shape, but for
### e.g. examples/hierarchical.ty the resulting images in the Test
### Pattern preview window are square (instead of the actual
### rectangular shapes), matching between the eyes (instead of the
### actual two different rectangles), and with dot sizes that don't
### match between the eyes.  It's not clear why this happens.

class RandomDotStereogram(PatternGenerator):
    """
    Random dot stereogram using rectangular black and white patches.

    Based on Matlab code originally from Jenny Read, reimplemented
    in Python by Tikesh Ramtohul (2006).
    """

    # Suppress unused parameters
    x = param.Number(precedence=-1)
    y = param.Number(precedence=-1)
    size = param.Number(precedence=-1)
    orientation = param.Number(precedence=-1)

    # Override defaults to make them appropriate
    scale  = param.Number(default=0.5)
    offset = param.Number(default=0.5)

    # New parameters for this pattern

    #JABALERT: Should rename xdisparity and ydisparity to x and y, and simply
    #set them to different values for each pattern to get disparity
    xdisparity = param.Number(default=0.0,bounds=(-1.0,1.0),softbounds=(-0.5,0.5),
                        precedence=0.50,doc="Disparity in the horizontal direction.")

    ydisparity = param.Number(default=0.0,bounds=(-1.0,1.0),softbounds=(-0.5,0.5),
                        precedence=0.51,doc="Disparity in the vertical direction.")

    dotdensity = param.Number(default=0.5,bounds=(0.0,None),softbounds=(0.1,0.9),
                        precedence=0.52,doc="Number of dots per unit area; 0.5=50% coverage.")

    dotsize    = param.Number(default=0.1,bounds=(0.0,None),softbounds=(0.05,0.15),
                        precedence=0.53,doc="Edge length of each square dot.")

    random_seed=param.Integer(default=500,bounds=(0,1000),
                        precedence=0.54,doc="Seed value for the random position of the dots.")


    def __call__(self,**params_to_override):
        p = ParamOverrides(self,params_to_override)

        xsize,ysize = SheetCoordinateSystem(p.bounds,p.xdensity,p.ydensity).shape
        xsize,ysize = int(round(xsize)),int(round(ysize))

        xdisparity  = int(round(xsize*p.xdisparity))
        ydisparity  = int(round(xsize*p.ydisparity))
        dotsize     = int(round(xsize*p.dotsize))

        bigxsize = 2*xsize
        bigysize = 2*ysize
        ndots=int(round(p.dotdensity * (bigxsize+2*dotsize) * (bigysize+2*dotsize) /
                        min(dotsize,xsize) / min(dotsize,ysize)))
        halfdot = floor(dotsize/2)

        # Choose random colors and locations of square dots
        random_seed = p.random_seed

        random_array.seed(random_seed*12,random_seed*99)
        col=where(random_array.random((ndots))>=0.5, 1.0, -1.0)

        random_array.seed(random_seed*122,random_seed*799)
        xpos=floor(random_array.random((ndots))*(bigxsize+2*dotsize)) - halfdot

        random_array.seed(random_seed*1243,random_seed*9349)
        ypos=floor(random_array.random((ndots))*(bigysize+2*dotsize)) - halfdot

        # Construct arrays of points specifying the boundaries of each
        # dot, cropping them by the big image size (0,0) to (bigxsize,bigysize)
        x1=xpos.astype(Int) ; x1=choose(less(x1,0),(x1,0))
        y1=ypos.astype(Int) ; y1=choose(less(y1,0),(y1,0))
        x2=(xpos+(dotsize-1)).astype(Int) ; x2=choose(greater(x2,bigxsize),(x2,bigxsize))
        y2=(ypos+(dotsize-1)).astype(Int) ; y2=choose(greater(y2,bigysize),(y2,bigysize))

        # Draw each dot in the big image, on a blank background
        bigimage = zeros((bigysize,bigxsize))
        for i in range(ndots):
            bigimage[y1[i]:y2[i]+1,x1[i]:x2[i]+1] = col[i]

        result = p.offset + p.scale*bigimage[ (ysize/2)+ydisparity:(3*ysize/2)+ydisparity ,
                                              (xsize/2)+xdisparity:(3*xsize/2)+xdisparity ]

        for of in p.output_fns:
            of(result)

        return result
