#!/usr/bin/env python3
import os
import igl
import click

import scipy as sp
import scipy.sparse as sparse
import numpy as np

import meshplot as mp

#----------------------------------------------------------------------------

def divergence(v, f):
    g = igl.grad(v, f)

    d_area = igl.doublearea(v, f)
    t = sparse.diags(np.hstack([d_area, d_area, d_area]) * 0.5)

    return -g.T.dot(t)

#----------------------------------------------------------------------------

def find_boundary_vertices(f):
    edges = np.vstack([f[:, [0, 1]], f[:, [1, 2]], f[:, [2, 0]]])
    edges_sorted = np.sort(edges, axis=1)
    edge_keys = edges_sorted[:, 0] * (edges_sorted.max() + 1) + edges_sorted[:, 1]
    unique, counts = np.unique(edge_keys, return_counts=True)
    boundary_edges = unique[counts == 1]
    boundary_sorted = np.column_stack([
        boundary_edges // (edges_sorted.max() + 1),
        boundary_edges % (edges_sorted.max() + 1)
    ])
    return np.unique(boundary_sorted.ravel())

#----------------------------------------------------------------------------

def compute_scale_factor(v_src, f_src, v_ref, f_ref, beta, gamma):
    _, _, k1, k2, _ = igl.principal_curvature(v_src, f_src)
    K = k1 * k2
    K = igl.average_onto_faces(f_src, K)
    absK = np.abs(K)

    if v_ref is not None and f_ref is not None:
        d_area_src = igl.doublearea(v_src, f_src)
        d_area_ref = igl.doublearea(v_ref, f_ref)
        area_ratio = np.where(
            (d_area_ref > 0) & (d_area_src > 0), d_area_src / d_area_ref, 1.0
        )
        gamma_per_face = beta * np.log(area_ratio)
    else:
        gamma_per_face = np.full(len(K), gamma)

    sf = np.where(absK > 0, np.power(absK, gamma_per_face), 0.0)
    sf = np.concatenate([sf, sf, sf])
    sf = np.stack([sf, sf, sf], axis=1)
    return sf

#----------------------------------------------------------------------------

def solve_with_boundary(L, b, v_src, f_src):
    n = v_src.shape[0]
    bnd = find_boundary_vertices(f_src)

    if len(bnd) == 0:
        bnd = np.array([0])

    num_bnd = len(bnd)
    B = sparse.coo_matrix(
        (np.ones(num_bnd), (np.arange(num_bnd), bnd)),
        shape=(num_bnd, n)
    ).tocsc()

    Z = sparse.csc_matrix((num_bnd, num_bnd))
    A = sparse.bmat([[L, B.T], [B, Z]], format='csc')

    result = np.zeros((n + num_bnd, 3))
    for dim in range(3):
        rhs = np.concatenate([b[:, dim], v_src[bnd, dim]])
        result[:, dim] = sparse.linalg.spsolve(A, rhs)

    return result[:n]

#----------------------------------------------------------------------------

def caricaturize(v_src, f_src, v_ref=None, f_ref=None, beta=0.1, gamma=0.5):
    L = igl.cotmatrix(v_src, f_src)

    div = divergence(v_src, f_src)
    grad = igl.grad(v_src, f_src)
    sf = compute_scale_factor(v_src, f_src, v_ref, f_ref, beta, gamma)
    b = div @ (sf * (grad @ v_src))

    return solve_with_boundary(L, b, v_src, f_src)

#----------------------------------------------------------------------------

@click.command()
@click.option('--outdir', help='Where to save the result .obj file', required=True, metavar='DIR')
@click.option('--src', help='Path for a source mesh .obj file', required=True, metavar='PATH')
@click.option('--ref', help='Path for a reference mesh .obj file (optional for reference-free mode)', default=None, metavar='PATH')
@click.option('--beta', help='Exaggeration degree for reference mode [default: 0.1]', type=float, default=0.1)
@click.option('--gamma', help='Constant exaggeration factor for reference-free mode [default: 0.5]', type=float, default=0.5)
@click.option('--meshplot', help='Enable to save .html file for mesh visualization by using meshplot', is_flag=True, default=False)
def main(outdir, src, ref, beta, gamma, meshplot):
    """
    Exaggerate an input 3D face mesh using the techniques described in the paper:\n
    "Computational Caricaturization of Surfaces", Sela et al., CVIU2015.

    Supports two modes:\n
    \b
    1. Reference mode (--ref provided): uses area ratio between source and reference
       python caricaturize.py --outdir=./ --ref=examples/ref.obj --src=examples/src.obj --beta=0.6
    \b
    2. Reference-free mode (no --ref): uses a constant gamma exaggeration factor
       python caricaturize.py --outdir=./ --src=examples/src.obj --gamma=0.5

    """
    v_src, f_src = igl.read_triangle_mesh(src)

    v_ref, f_ref = None, None
    if ref is not None:
        v_ref, f_ref = igl.read_triangle_mesh(ref)

    v_exag = caricaturize(v_src, f_src, v_ref, f_ref, beta=beta, gamma=gamma)

    out_path = os.path.join(outdir, 'output.obj')
    igl.write_triangle_mesh(out_path, v_exag, f_src)
    print(f'The output mesh is successfully saved at {out_path}')

    if meshplot:
        mp.offline()
        mp.plot(v_src, f_src, filename=os.path.join(outdir, 'source.html'))
        mp.plot(v_exag, f_src, filename=os.path.join(outdir, 'output.html'))

#----------------------------------------------------------------------------

if __name__ == '__main__':
    main()
