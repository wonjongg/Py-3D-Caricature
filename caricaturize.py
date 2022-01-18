#!/usr/bin/env python3
import os
import igl
import click

import scipy as sp
import numpy as np

import pymesh as pm
import meshplot as mp

#----------------------------------------------------------------------------

def divergence(v, f):
    l = igl.cotmatrix(v, f)
    g = igl.grad(v, f)

    d_area = igl.doublearea(v, f)
    t = sp.sparse.diags(np.hstack([d_area, d_area, d_area]) * 0.5)

    return  -g.T.dot(t)

#----------------------------------------------------------------------------

def caricaturization_ref(v_src, f_src, v_ref, f_ref, beta=0.1):
    # Left hand matrix
    L = igl.cotmatrix(v_src, f_src)

    # Right hand vector
    div = divergence(v_src, f_src)
    grad = igl.grad(v_src, f_src)
    v1, v2, k1, k2 = igl.principal_curvature(v_src, f_src)
    K = k1 * k2
    K = igl.average_onto_faces(f_src, K)
    d_area_src = igl.doublearea(v_src, f_src)
    d_area_ref = igl.doublearea(v_ref, f_ref)

    gamma = beta * np.log(d_area_src / d_area_ref)
    scale_factor = np.power(np.abs(K), gamma)
    scale_factor = np.concatenate([scale_factor, scale_factor, scale_factor])
    scale_factor = np.stack([scale_factor, scale_factor, scale_factor], axis=1)
    b = div * (scale_factor * (grad * v_src)) 

    # Solve
    solver = pm.SparseSolver.create('LDLT')
    solver.compute(L)
    v = solver.solve(b)

    return v

#----------------------------------------------------------------------------

@click.command()
@click.option('--outdir', help='Where to save the result .obj file', required=True, metavar='DIR')
@click.option('--ref', help='Path for a reference mesh .obj file', required=True, metavar='PATH')
@click.option('--src', help='Path for a source mesh .obj file', required=True, metavar='PATH')
@click.option('--beta', help='Exaggeration degree value [default: 0.1]', type=float, default=0.1)
@click.option('--meshplot', help='Enable to save .html file for mesh visualization by using meshplot', type=bool, metavar='BOOL')
def main(outdir, ref, src, beta, meshplot):
    """
    Exaggerate an input 3D face mesh using the techniques described in the paper:\n
    "Computational Caricaturization of Surfaces", Sela et al., CVIU2015.

    Usage examples:

    \b
    python caricaturize.py --outdir=./ --ref=examples/ref.obj --src=examples/src.obj --beta=0.6
    
    """
    try:
        v_ref, f_ref = igl.read_triangle_mesh(ref)
        v_src, f_src = igl.read_triangle_mesh(src)
    except:
        raise Exception("Please check .obj files or paths")
    
    try:
        v_exag = caricaturization_ref(v_src, f_src, v_ref, f_ref, beta=beta)
    except:
        raise Exception("Please check that topologies of source and reference meshes are the same")

    try:
        success = igl.write_triangle_mesh(os.path.join(outdir, 'output.obj'), v_exag, f_src)
        if success:
            print(f'The output mesh is successfully saved at {os.path.join(outdir, "output.obj")}')
    except:
        raise Exception('Saving th result mesh is failed.')

    if meshplot:
        mp.offline()
        mp.plot(v_src, f_src)
        mp.plot(v_exag, f_src)

#----------------------------------------------------------------------------

if __name__ == '__main__':
    main()
