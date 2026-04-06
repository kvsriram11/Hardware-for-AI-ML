# Hardware for AI and Machine Learning

## Author
Venkata Sriram Kamarajugadda

## Course
ECE510: Hardware for AI/ML  
Spring 2026

## Instructor
Prof. Christof Teuscher

## Tentative project topic
Hardware accelerator for reservoir computing with focus on efficient reservoir state update for streaming data

## Repository purpose
This repository contains my work for the ECE510 Hardware for AI/ML course, including codefests and the main project.

## Project overview
The project is about building a hardware accelerator for a key part of a reservoir computing model called an Echo State Network.

The main computation is:
x(t) = f(W_res x(t-1) + W_in u(t))

This project focuses on speeding up this computation using hardware. The goal is to make it more efficient compared to running it on a normal CPU.

The target use case is time-series data such as spoken digit classification, where data comes in as a stream over time.

## Tools and technologies
SystemVerilog for hardware design  
Python for baseline and testing  
OpenLane for synthesis  
AXI interface for connecting the design to a host system  

## Repository structure
codefest contains codefest submissions  
project contains the main project work  

## License
This project is released under the MIT License.
