# Project Description
    The Game: Swiss Jass

## Content
1. Mission
2. Scope
3. Objectives and success criteria
4. Inputs/Outputs
5. Constraints
6. Risks & mitigation strategies


## 1. Mission
A short description of one or a few sentences, structured similar to:
We will build X for Y to enable Z under constraints C.

Here are some examples from last year:
- A 2D seismic wave simulator for researchers to explore heterogeneity effects on travel times running on a laptop.
- A dashboard where users can drop in datasets and perform exploratory data analysis and visualizations.
- An online, multi-user version of the game ”Br¨andi Dog”.
- Am orbital animation GUI where users can define andsimulate solar systems in 2D.



## 2. Scope
You will outline the scope, the ”what” and ”how much” of the
project:
- In scope (3–5 bullets)
- Out of scope / non-goals (at least 3 bullets)

Non-goal examples:
- No distributed computing
- No GPU acceleration until baseline is correct
- Not a Graphical User Interface



  
## 3. Objectives and success criteria
You will define SMART objectives; 
Specific, Measurable,Achievable, Relevant, and Time-bound.

The objectives will directly address your projects’ Scientific: 

### Validity
May include analytic benchmarking, error tolerance, application on known datasets, reproducibility, ...

### Operational performance
Runtime/memory targets, readabilityand reusability,multi-platform operability...




## 4. Inputs/Outputs
Early on, you will specify (not a full list):
- Data formats: For example, NetCDF, GeoTIFF, HDF5, CSV, shapefiles, . . .
- Scale: image size, grid size, timesteps, file sizes, . . .
- Units/coordinates: meters vs degrees, reference frames, time bases, . . .
- Metadata: rasters/vectors, plots, reports, logs, . . . or anything produced as outcome of the project.

While this may change along the way, it will drive the boundaries of
your project and focus your work.


## 5. Constraints
You will come up with constraints for your project, including, but
not limited to:
- Compute: CPU/GPU, RAM limits, . . .
- Runtime: interactive vs batch
- Dependencies: libraries, licensing, . . .
- Data governance: sensitive/embargoed data
- Platform: Windows, mac, Linux, . . .

## 6. Risks & mitigation strategies
You will come up with potential risks and possible mitigation plans.

| *Risk*                    | *Mitigation* |
| ------------------------- | -----------  |
| Data Inconsistencies      | Implement a Data Validation Layer using filtering or preprocessing scripts.    |
| Numerical Stability       | Use Assertion Testing and boundarytests to evaluate numerical overflows.       |
| Library Incompatibility   | Utilize Environment Encapsulation (e.g., Docker, Conda, or requirements.txt) to lock depen-dency versions and ensure portabilityacross systems.        |
    
