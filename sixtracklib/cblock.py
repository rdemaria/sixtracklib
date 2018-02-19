""" Manage block
"""
import os

import numpy as np

from .cobjects import CProp, CObject, CBuffer


modulepath=os.path.dirname(os.path.abspath(__file__))

try:
  import pyopencl as cl
  os.environ['PYOPENCL_COMPILER_OUTPUT']='1'
  srcpath='-I%s'%modulepath
  src=open(os.path.join(modulepath,'block.c')).read()
  ctx = cl.create_some_context(interactive=False)
  prg=cl.Program(ctx,src).build(options=[srcpath])
  queue = cl.CommandQueue(ctx)
  mf = cl.mem_flags
  rw=mf.READ_WRITE | mf.COPY_HOST_PTR
except ImportError:
  print("Warning: error import OpenCL: track_cl not available")
  cl=False
  pass



class Drift(CObject):
    objid  = CProp('u64',0,default=2)
    length = CProp('f64',1,default=0)

class DriftExact(CObject):
    objid  = CProp('u64',0,default=3)
    length = CProp('f64',1,default=0)

class Multipole(CObject):
    objid  = CProp('u64',0,default=4)
    order  = CProp('f64',1,default=0,const=True)
    length = CProp('f64',2,default=0)
    hxl    = CProp('f64',3,default=0)
    hyl    = CProp('f64',4,default=0)
    bal    = CProp('f64',5,default=0,length='2*(order+1)')
    def __init__(self,knl=[],ksl=[],**nvargs):
      if len(knl)>len(ksl):
          ksl+=[0]*(len(knl)-len(ksl))
      else:
          knl+=[0]*(len(ksl)-len(knl))
      bal=np.array(sum(zip(knl,ksl),()))
      fact=1
      for n in range(len(bal)//2):
          bal[n*2:n*2+2]/=fact
      if len(bal)>=2 and len(bal)%2==0:
          order=len(bal)/2-1
      else:
          raise ValueError("Size of bal must be even")
      nvargs['bal']=bal
      nvargs['order']=order
      CObject.__init__(self,**nvargs)



class CBlock(object):
    """ Block object
    """
    _elem_types = dict(Drift      = 2,
                      DriftExact = 3,
                      Multipole  = 4,
                      Cavity     = 5,
                      Align      = 6,
                      Block      = 7)

    def __init__(self):
        self._cbuffer=CBuffer(1)
        self.nelems=0
        self.elem={}
        self.elem_ids=[]
        self.elem_revnames={}
    def _add_elem(self,name,elem):
        self.elem[self.nelems]=elem
        self.elem.setdefault(name,[]).append(elem)
        self.elem_revnames[elem._offset]=name
        self.elem_ids.append(elem._offset)
        self.nelems+=1
    def add_Drift(self,name=None,**nvargs):
        elem=Drift(cbuffer=self._cbuffer,**nvargs)
        self._add_elem(name,elem)
    def add_Multipole(self,name=None,**nvargs):
        elem=Multipole(cbuffer=self._cbuffer,**nvargs)
        self._add_elem(name,elem)
    if cl:
        def track_cl(self,particles,nturns=1,elembyelem=None,turnbyturn=None):
            CParticles=particles.__class__
            npart=np.int64(particles.npart)
            #uint bug in boost/pyopencl/numpy???
            particles_g=cl.Buffer(ctx, rw, hostbuf=particles._data)
            #ElemByElem data
            if elembyelem is True:
              elembyelem=Beam(npart=npart*self.nelems*nturn+1)
            if elembyelem is None:
              elembyelem_g=cl.Buffer(ctx, rw, hostbuf=np.array([-1]))
            else:
              elembyelem_g=cl.Buffer(ctx, rw, hostbuf=elembyelem._data)
            #TurnByTurn data
            if turnbyturn is True:
              turnbyturn=Beam(npart=npart*nturn+1)
            if turnbyturn is None:
              turnbyturn_g=cl.Buffer(ctx, rw, hostbuf=np.array([-1]))
            else:
              turnbyturn_g=cl.Buffer(ctx, rw, hostbuf=self.turnbyturn._data)
            #Tracking data
            elems_g=cl.Buffer(ctx, rw, hostbuf=self._cbuffer.data)
            elemids=np.array(self.elem_ids,dtype='uint64')
            elemids_g=cl.Buffer(ctx, rw, hostbuf=elemids)
            nelems=np.int64(self.nelems)
            nturns=np.int64(nturns)
            prg.Block_track(queue,[npart],None,
                            elems_g, elemids_g, nelems,
                            nturns,
                            particles_g, elembyelem_g, turnbyturn_g)
            cl.enqueue_copy(queue,particles._data,particles_g)
            if turnbyturn:
                cl.enqueue_copy(queue,turnbyturn._data,turnbyturn_g)
            if elembyelem:
                cl.enqueue_copy(queue,elembyelem._data,elembyelem_g)
            return particles,elembyelem, turnbyturn



