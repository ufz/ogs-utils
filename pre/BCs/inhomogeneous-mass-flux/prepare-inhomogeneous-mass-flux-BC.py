#!/usr/bin/env pvpython
# -*- coding: utf-8 -*-

from __future__ import print_function

import inspect

import argparse
parser = argparse.ArgumentParser()
parser.add_argument("--input", type=str, required=True)
parser.add_argument("--output", type=str, required=True)
parser.add_argument("--profile", type=str, required=True)
parser.add_argument("--total-flux", type=float, required=True)
parser.add_argument("--slice-normal", type=float, nargs=3, required=True)
parser.add_argument("--slice-origin", type=float, nargs=3, required=True)

args = parser.parse_args()

#### import the simple module from the paraview
from paraview.simple import *
#### disable automatic camera reset on 'Show'
paraview.simple._DisableFirstRenderCameraReset()

# create a new 'XML Unstructured Grid Reader'
xMLUnstructuredGridReader1 = XMLUnstructuredGridReader(FileName=[args.input])


def do_enumerate_points():
    data = self.GetInputDataObject(0, 0)

    # point_ids = vtk.vtkIdTypeArray()  ## TODO why does that not work?
    # point_ids = vtk.vtkLongArray()
    point_ids = vtk.vtkUnsignedLongArray()
    point_ids.SetName("bulk_node_ids")
    point_ids.SetNumberOfComponents(1)
    N = data.GetPoints().GetNumberOfPoints()
    point_ids.SetNumberOfTuples(N)

    for i in range(N):
        point_ids.SetComponent(i, 0, i)

    self.GetOutputDataObject(0).GetPointData().AddArray(point_ids)

    ### Cell ids do not work like that:
    # cell_ids = vtk.vtkDoubleArray()
    # cell_ids.SetName("bulk_mesh_element_ids")
    # cell_ids.SetNumberOfComponents(1)
    # C = data.GetCellData().GetNumberOfTuples()
    # cell_ids.SetNumberOfTuples(N)

    # for i in range(C):
    #     cell_ids.SetComponent(i, 0, i)

    # self.GetOutputDataObject(0).GetCellData().AddArray(cell_ids)


enumerate_points = ProgrammableFilter(Input=xMLUnstructuredGridReader1)
enumerate_points.Script = inspect.getsource(do_enumerate_points) + "\n\ndo_enumerate_points()"
enumerate_points.RequestInformationScript = ''
enumerate_points.RequestUpdateExtentScript = ''
enumerate_points.PythonPath = ''
enumerate_points.CopyArrays = 0


# create a new 'Slice'
slice1 = Slice(Input=enumerate_points)
slice1.SliceType = 'Plane'
slice1.Triangulatetheslice = 0
slice1.SliceOffsetValues = [0.0]

# init the 'Plane' selected for 'SliceType'
slice1.SliceType.Origin = args.slice_origin
slice1.SliceType.Normal = args.slice_normal


# Trick from http://www.vtk.org/Wiki/VTK/Examples/Cxx/PolyData/PolyDataToUnstructuredGrid
# for converting slice's polydata to an unstructured grid
appendDatasets1 = AppendDatasets(Input=slice1)


def do_compute_mass_flux():
    import numpy as np
    from scipy.interpolate import interp1d
    from vtk.util.numpy_support import vtk_to_numpy, numpy_to_vtk

    data = self.GetInputDataObject(0, 0)

    ### compute predefined mass flux

    mu  = 21.90e-6 # Pa s
    rho = 0.9333 # kg/m³

    csv = args.profile
    rs, velocities = np.loadtxt(csv, unpack=True, usecols=(0,1))
    velocity_fct = interp1d(rs, velocities)

    # compute total flux as "seen" by the discrete grid
    rs_grid = vtk_to_numpy(data.GetPoints().GetData())[:,0]
    vs_grid = velocity_fct(rs_grid)

    mass_flux = vs_grid * rho

    total_flux = 2*np.pi * np.trapz(y=rs_grid * mass_flux, x=rs_grid)

    scale_factor = args.total_flux / total_flux

    print("total flux from given profile:", total_flux, "[e.g. kg/s]")
    print("requested total flux:", args.total_flux, "kg/s")
    print("scale factor:", scale_factor)

    mass_flux *= scale_factor
    mass_flux = numpy_to_vtk(mass_flux, 1)
    mass_flux.SetName("mass_flux")

    self.GetOutputDataObject(0).GetPointData().AddArray(mass_flux)


mass_flux = ProgrammableFilter(Input=appendDatasets1)
mass_flux.Script = inspect.getsource(do_compute_mass_flux) + "\n\ndo_compute_mass_flux()"
mass_flux.RequestInformationScript = ''
mass_flux.RequestUpdateExtentScript = ''
mass_flux.PythonPath = ''
mass_flux.CopyArrays = 1

# ----------------------------------------------------------------
# finally, restore active source
SetActiveSource(mass_flux)
# ----------------------------------------------------------------

# save data
SaveData(args.output, proxy=mass_flux, DataMode='Binary',
    EncodeAppendedData=1,
    CompressorType='ZLib')

