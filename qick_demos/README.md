A high-level overview of the QICK software capabilities
=================================================

Below is a brief summary of the QICK software capabilities.

## Sending and receiving pulses
* Basic example given in [Demo 00_Send_receive_pulse](https://github.com/openquantumhardware/qick/blob/main/qick_demos/00_Send_receive_pulse.ipynb)
* Control of 1st and 2nd Nyquist zone pulses, direct synthesis of pulses up to 6 GHz
* Decimated mode and acquire (I/Q) mode (with round-robin style data acquisition)
* Arbitrary pulse envelopes
* DAC modes of operation: CW mode, product mode, envelope-only mode
* ADC modes of operation: demodulation in the ADC
* Relative timing and phase control between pulses

## Sweeping variables within a QICK program
* Basic example given in [Demo 02_Sweeping_variables](https://github.com/openquantumhardware/qick/blob/main/qick_demos/02_Sweeping_variables.ipynb)
* The update function allows you to easily update parameters such as pulse gain in a fast loop (within a QICK program, rather than a Python slow loop over multiple QICK programs)

## Conditional logic within a QICK program
* Basic example given in [Demo 03_Conditional_logic](https://github.com/openquantumhardware/qick/blob/main/qick_demos/03_Conditional_logic.ipynb)
* The ability to play conditional pulses based on tProc register values

## Reading, math and writing within a QICK program
* Basic example given in [Demo 04_Reading_Math_Writing](https://github.com/openquantumhardware/qick/blob/main/qick_demos/04_Reading_Math_Writing.ipynb)
* The ability to write data to and read data from tProc memory addresses (which tProc registers can access) 
* Addition, subtraction, multiplication, bit shifting

## Measurements on quantum devices

* Measuring a single qubit [Demo 06_qubit_demos](https://github.com/openquantumhardware/qick/blob/main/qick_demos/06_qubit_demos.ipynb)
* N-dimensional sweeps [Demo 07_Sweep_ND_variables](https://github.com/openquantumhardware/qick/blob/main/qick_demos/07_Sweep_ND_variables.ipynb)
* Learn how labs have used the QICK! Check out [our papers page](https://qick-docs.readthedocs.io/latest/papers.html)

## Capturing experiment provenance with Dataerai
* Basic example given in [Demo 10_Dataerai_provenance](https://github.com/openquantumhardware/qick/blob/main/qick_demos/10_Dataerai_provenance.ipynb)
* Automatically upload a run's configuration, raw data, and analysis to [Dataerai](https://dataerai.com) as linked, traceable assets using the bundled `qick_dataerai` package
* The demo notebook runs end-to-end **without a board or a Dataerai login** (it uses a local recording client and simulated data), then shows how to swap in the real client

## Other examples of QICK measurement code, shared by QICK collaborators

* [IEEE Quantum Week 2023 QICK tutorial](https://github.com/openquantumhardware/QCE2023_public)
* [Connie Miao, Schuster Lab](https://github.com/conniemiao/slab_rfsoc_expts)
* [Chao Zhou, Hatlab](https://github.com/PITT-HATLAB/Hatlab_RFSOC)
