from distutils import core
import numpy as np
from emepy.fd import MSEMpy, ModeSolver
from emepy.models import Layer
from shapely.geometry import Polygon, Point
import geopandas as gdp


class Geometry(object):
    """Geoemtries are not required for users, however they do allow for easier creation of complex structures"""

    def __init__(self, layers: list) -> None:
        """Constructors should take in parameters from the user and build the layers"""
        self.layers = layers

    def __iter__(self):
        return iter(self.layers)


class Params(object):
    def __init__(self) -> None:
        return

    def get_solver_rect(self) -> ModeSolver:
        return

    def get_solver_index(self) -> ModeSolver:
        return


class EMpyGeometryParameters(Params):
    def __init__(
        self,
        wavelength: float = 1.55e-6,
        cladding_width: float = 2.5e-6,
        cladding_thickness: float = 2.5e-6,
        core_index: float = None,
        cladding_index: float = None,
        x: "np.ndarray" = None,
        y: "np.ndarray" = None,
        mesh: int = 128,
        accuracy: float = 1e-8,
        boundary: str = "0000",
        PML: bool = False,
        **kwargs,
    ):
        """Creates an instance of EMpyGeometryParameters which is used for abstract geometries that use EMpy as the solver"""

        self.wavelength = wavelength
        self.cladding_width = cladding_width
        self.cladding_thickness = cladding_thickness
        self.core_index = core_index
        self.cladding_index = cladding_index
        self.x = x
        self.y = y
        self.mesh = mesh
        self.accuracy = accuracy
        self.boundary = boundary
        self.PML = PML
        for key, val in kwargs.items():
            setattr(key, val)

    def get_solver_rect(
        self, width: float = 0.5e-6, thickness: float = 0.22e-6, num_modes: int = 1
    ) -> "MSEMpy":
        """Returns an EMPy solver that represents a simple rectangle"""

        return MSEMpy(
            wavelength=self.wavelength,
            width=width,
            thickness=thickness,
            num_modes=num_modes,
            cladding_width=self.cladding_width,
            cladding_thickness=self.cladding_thickness,
            core_index=self.core_index,
            cladding_index=self.cladding_index,
            x=self.x,
            y=self.y,
            mesh=self.mesh,
            accuracy=self.accuracy,
            boundary=self.boundary,
            PML=self.PML,
        )

    def get_solver_index(
        self, thickness: float = None, num_modes: int = None, n: "np.ndarray" = None
    ) -> "MSEMpy":
        """Returns an EMPy solver that represents the provided index profile"""

        return MSEMpy(
            wavelength=self.wavelength,
            width=None,
            thickness=thickness,
            num_modes=num_modes,
            cladding_width=self.cladding_width,
            cladding_thickness=self.cladding_thickness,
            core_index=self.core_index,
            cladding_index=self.cladding_index,
            x=self.x,
            y=self.y,
            mesh=self.mesh,
            accuracy=self.accuracy,
            boundary=self.boundary,
            n=n,
            PML=self.PML,
        )


class DynamicPolygon(Geometry):
    """Creates a polygon in EMEPy given a list of solid vertices and changeable vertices and can be changed for shape optimization"""

    def get_design(self) -> list:
        """Returns the design region as a list of parameters"""
        return self.design


class DynamicRect2D(DynamicPolygon):
    def __init__(
        self,
        params: Params = EMpyGeometryParameters(),
        width: float = 0.5e-6,
        length: float = 1e-6,
        num_params: int = 10,
        symmetry: bool = False,
        subpixel: bool = True,
        mesh_z: int = 10,
    ) -> None:
        """Creates an instance of DynamicPolygon2D

        Parameters
        ----------

        """
        self.params = params
        self.symmetry = symmetry
        self.subpixel = subpixel
        self.width, self.length = (width, length)
        self.grid_x = (
            params.x
            if params.x is not None
            else np.linspace(
                -params.cladding_width / 2, params.cladding_width / 2, params.mesh
            )
        )
        self.grid_z = np.linspace(0, length, mesh_z)

        # Set left side static vertices
        x = [-width / 2, width / 2]
        z = [0, 0]
        self.static_vertices_left = list(zip(x, z))

        # Set top dynamic vertices
        z = np.linspace(0, length, num_params + 2)[1:-1].tolist()
        x = (
            np.array([width / 2] * num_params)
            + np.sin(np.array(z) / length * np.pi) * width / 2
        )
        dynamic_vertices_top = list(zip(x, z))

        # Set right side static vertices
        x = [width / 2, -width / 2]
        z = [length, length]
        self.static_vertices_right = list(zip(x, z))

        # Set bottom dynamic vertices
        x = [-width / 2] * num_params
        z = np.linspace(0, length, num_params + 2)[1:-1][::-1].tolist()
        dynamic_vertices_bottom = list(zip(x, z))

        # Establish design
        design = (
            dynamic_vertices_top[:]
            if symmetry
            else dynamic_vertices_top + dynamic_vertices_bottom
        )
        design = [i for j in design for i in j]

        # Set design
        self.set_design(design)

    def set_design(self, design: list):
        """Sets the design region parameters"""
        self.design = design
        return self.set_layers()

    def get_n(self):
        """Will form the refractive index map given the current parameters"""
        # Create vertices
        vertices = []

        # Add static left vertices
        vertices += self.static_vertices_left

        # Add top design
        top = self.design if self.symmetry else self.design[: len(self.design) // 2]
        vertices += [(x, z) for x, z in zip(top[:-1:2], top[1::2])]

        # Add static right vertices
        vertices += self.static_vertices_right

        # Add bottom design
        bottom = self.design if self.symmetry else self.design[len(self.design) // 2 :]
        if self.symmetry:
            vertices += [
                (-x, z) for x, z in list(zip(bottom[:-1:2], bottom[1::2]))[::-1]
            ]
        else:
            vertices += [(x, z) for x, z in list(zip(bottom[:-1:2], bottom[1::2]))]

        # Form polygon
        # polygon = Polygon(vertices)
        polygon = Point(0, self.length / 2).buffer(self.width / 2)

        # Form grid
        x, z = (self.grid_x, self.grid_z)
        xx, zz = np.meshgrid(x, z)
        n = np.zeros(xx.shape)[:-1, :-1]

        # Apply subpixel
        xlower, xupper = (x[:-1], x[1:])
        zlower, zupper = (z[:-1], z[1:])
        for i, xp in enumerate(zip(xlower, xupper)):
            for j, zp in enumerate(zip(zlower, zupper)):

                # Upper and lower points
                xl, xu = xp
                zl, zu = zp
                total_area = (xu - xl) * (zu - zl)

                # Create polygon of the pixel
                pixel_poly = Polygon([(xl, zl), (xl, zu), (xu, zu), (xu, zl)])

                # Get overlapping area
                overlapping_area = 0
                if pixel_poly.intersects(polygon):
                    overlapping_area = pixel_poly.intersection(polygon).area

                # Calculate effective index
                if self.subpixel:
                    n[j, i] = (
                        overlapping_area / total_area * self.params.core_index
                        + (1 - overlapping_area / total_area)
                        * self.params.cladding_index
                    )
                elif overlapping_area:
                    n[j, i] = self.params.core_index
                else:
                    n[j, i] = self.params.cladding_index

        return n

    def set_layers(self):
        """Creates the layers needed for the geometry"""

        n = self.get_n()
        return n


# def run(radius=1e-6, subpixel=True):
#     dd = DynamicRect2D(
#         EMpyGeometryParameters(mesh=50, core_index=3.4, cladding_index=1.4),
#         radius,
#         2.5e-6,
#         symmetry=True,
#         mesh_z=50,
#         subpixel=subpixel,
#     )
#     n1 = dd.set_design(dd.get_design())
#     xx = ((dd.grid_z - 1.25e-6)[1:] + (dd.grid_z - 1.25e-6)[:-1]) / 2
#     yy = ((dd.grid_x - 1.25e-6)[1:] + (dd.grid_x - 1.25e-6)[:-1]) / 2
#     ms = MSEMpy(wl=1.55e-6, n=n1, x=xx, y=yy, num_modes=1)
#     ms.solve()
#     return ms.get_mode()


# with_smoothing = []
# without_smoothing = []
# alt = np.linspace(0, 10e-9, 20)

# for i, d in enumerate(alt):
#     mode1 = run(1e-6, True)
#     mode2 = run(1e-6 + d, True)
#     mode3 = mode1 - mode2
#     mode3.n = mode2.n - mode1.n
#     with_smoothing.append(np.real(mode1.neff - mode2.neff))

#     mode1 = run(1e-6, False)
#     mode2 = run(1e-6 + d, False)
#     mode3 = mode1 - mode2
#     mode3.n = mode2.n - mode1.n
#     without_smoothing.append(np.real(mode1.neff - mode2.neff))

# from matplotlib import pyplot as plt

# plt.figure()
# plt.plot(alt, with_smoothing, label="With smoothing")
# plt.plot(alt, without_smoothing, label="Without smoothing")
# plt.xlabel("Radius change")
# plt.ylabel("delta neff")
# plt.legend()
# plt.show()


# from matplotlib import pyplot as plt

# plt.figure()
# mode2.plot_material()
# plt.show()
# plt.figure()
# mode1.plot_material()
# plt.show()


# plt.figure()
# plt.imshow(
#     np.rot90(n1),
#     cmap="Greys",
#     extent=[
#         (dd.grid_z - 1.25e-6)[0],
#         (dd.grid_z - 1.25e-6)[-1],
#         dd.grid_x[0],
#         dd.grid_x[-1],
#     ],
#     interpolation="none",
# )
# plt.xlabel("z")
# plt.ylabel("x")
# plt.colorbar()
# plt.show()

# # Create layers

# dd = DynamicRect2D(
#     EMpyGeometryParameters(mesh=50, core_index=3.4, cladding_index=1.4),
#     1e-6 + 1e-12,
#     2.5e-6,
#     symmetry=True,
#     mesh_z=50,
#     subpixel=True,
# )
# n2 = dd.set_design(dd.get_design())
# n = n2 - n1

# plt.figure()
# plt.imshow(
#     np.rot90(n),
#     cmap="RdBu",
#     extent=[dd.grid_z[0], dd.grid_z[-1], dd.grid_x[0], dd.grid_x[-1]],
#     interpolation="none",
# )
# plt.xlabel("z")
# plt.ylabel("x")
# plt.colorbar()
# plt.show()


class Waveguide(Geometry):
    """Block forms the simplest geometry in emepy, a single layer with a single waveguide defined"""

    def __init__(
        self,
        params: Params = EMpyGeometryParameters(),
        width: float = 0.5e-6,
        thickness: float = 0.22e-6,
        length: float = 1e-6,
        num_modes: int = 1,
    ) -> None:
        """Creates an instance of block which can be called to access the required layers for solving

        Parameters
        ----------
        params : Params
            Geometry Parameters object containing large scale parameters
        width : number
            width of the core in the cross section
        thickness : number
            thickness of the core in the cross section
        length : number
            length of the structure
        num_modes : int
            number of modes to solve for (default:1)
        """

        mode_solver = params.get_solver_rect(width, thickness, num_modes)
        layers = [Layer(mode_solver, num_modes, params.wavelength, length)]
        super().__init__(layers)


class WaveguideChannels(Geometry):
    def __init__(
        self,
        params: Params = EMpyGeometryParameters(),
        width: float = 0.5e-6,
        thickness: float = 0.22e-6,
        length: float = 1e-6,
        num_modes: int = 1,
        gap: float = 0.1e-6,
        num_channels: int = 2,
        exclude_indices: list = [],
    ) -> None:

        # Create n
        starting_center = -0.5 * (num_channels - 1) * (gap + width)
        n_output = np.ones(params.mesh) * params.cladding_index
        for out in range(num_channels):
            if out not in exclude_indices:
                center = starting_center + out * (gap + width)
                left_edge = center - 0.5 * width
                right_edge = center + 0.5 * width
                n_output = np.where(
                    (left_edge <= params.x) * (params.x <= right_edge),
                    params.core_index,
                    n_output,
                )

        # Create modesolver
        output_channel = params.get_solver_index(thickness, num_modes, n_output)

        # Create layers
        self.layers = [Layer(output_channel, num_modes, params.wavelength, length)]
        super().__init__(self.layers)


class BraggGrating(Geometry):
    def __init__(
        self,
        params_left: Params = EMpyGeometryParameters(),
        params_right: Params = EMpyGeometryParameters(),
        width_left: float = 0.4e-6,
        thickness_left: float = 0.22e-6,
        length_left: float = 1e-6,
        width_right: float = 0.6e-6,
        thickness_right: float = 0.22e-6,
        length_right: float = 1e-6,
        num_modes: int = 1,
    ) -> None:

        # Create waveguides
        waveguide_left = Waveguide(
            params_left, width_left, thickness_left, length_left, num_modes
        )
        waveguide_right = Waveguide(
            params_right, width_right, thickness_right, length_right, num_modes
        )

        # Create layers
        self.layers = [*waveguide_left, *waveguide_right]
        super().__init__(self.layers)


class DirectionalCoupler(Geometry):
    def __init__(
        self,
        params: Params = EMpyGeometryParameters(),
        width: float = 0.5e-6,
        thickness: float = 0.22e-6,
        length: float = 25e-6,
        gap: float = 0.2e-6,
        num_modes: int = 1,
    ) -> None:

        # Create input waveguide channel
        input = WaveguideChannels(
            params, width, thickness, length, num_modes, gap, 2, exclude_indices=[1]
        )

        # Create main directional coupler
        coupler = WaveguideChannels(
            params, width, thickness, length, num_modes, gap, 2, exclude_indices=[]
        )

        # Create layers
        self.layers = [*input, *coupler]
        super().__init__(self.layers)
