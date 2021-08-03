from emepy.fd import MSLumerical # Requires Lumerical API
from emepy.fd import MSEMpy  # Open source
from emepy.eme import Layer, EME

import numpy as np
from matplotlib import pyplot as plt

num_periods = 50  # Number of Periods for Bragg Grating
length = 0.155  # Length of each segment of BG, Period = Length * 2
num_wavelengths = 10  # Number of wavelengths to sweep
wl_lower = 1.5  # Lower wavelength bound
wl_upper = 1.6  # Upper wavelength bound
num_modes = 1  # Number of Modes
mesh = 128
modesolver = MSLumerical

t = []  # Array that holds the transmission coefficients for different wavelengths

for wavelength in np.linspace(wl_lower, wl_upper, num_wavelengths):

    mode_solver1 = modesolver(
        wavelength * 1e-6,
        0.46e-6,
        0.22e-6,
        mesh=mesh,
        num_modes=num_modes,
        # lumapi_location="/Applications/Lumerical v202.app/Contents/API/Python",
    )  # First half of bragg grating

    mode_solver2 = modesolver(
        wavelength * 1e-6,
        0.54e-6,
        0.22e-6,
        mesh=mesh,
        num_modes=num_modes,
        # lumapi_location="/Applications/Lumerical v202.app/Contents/API/Python",
    )  # Second half of bragg grating

    layer1 = Layer(mode_solver1, num_modes, wavelength * 1e-6, length * 1e-6)  # First half of bragg grating
    layer2 = Layer(mode_solver2, num_modes, wavelength * 1e-6, length * 1e-6)  # Second half of bragg grating

    eme = EME([layer1, layer2], num_periods)  # Periodic EME will save computational time for repeated geometry

    # eme.draw() # Draw the structure

    eme.propagate()  # propagate at given wavelength

    t.append(np.abs((eme.get_s_params())[0, 0, num_modes]) ** 2)  # Grab the transmission coefficient
    print(t[-1])

# Plot the results
plt.plot(np.linspace(wl_lower, wl_upper, num_wavelengths), t)
plt.title("BG Bode Plot Periods=" + str(num_periods))
plt.xlabel("Wavelength (microns)")
plt.ylabel("t")
plt.show()
