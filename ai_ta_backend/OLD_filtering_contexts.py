# Env for kastan:

import inspect
import json
import os
import time
import traceback
from dotenv import load_dotenv

import openai
import ray
import replicate
import requests
from langchain import hub

load_dotenv(override=True)

## Local LLMs  USAGE DOCS: https://kastanday.notion.site/LLM-Serving-on-prem-OpenAI-Clone-bb06028266d842b0872465f552684177 ##

from transformers import AutoTokenizer

tokenizer = AutoTokenizer.from_pretrained("HuggingFaceH4/zephyr-7b-beta")

USER_QUERY = "Explain how tiling helps with global memory bandwidth."

CONTEXTS = [{
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        11,
    "readable_filename":
        "ece408-lecture5-CUDA-tiled-matrix-multiplication-vk-FA23.pdf",
    "s3_path":
        "courses/ECE408FA23/ece408-lecture5-CUDA-tiled-matrix-multiplication-vk-FA23.pdf",
    "text":
        "Shared Memory Tiling Basic Idea\nThread \n1\n2Thread \n\nData in Global Memory\nThread \n1\n2Thread \n\nShared Memory\n11\nData in Global Memory\n David Kirk/NVIDIA and Wen-mei W. Hwu, 2007-2018 \nECE408/CS483/ University of Illinois at Urbana-Champaign",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        20,
    "readable_filename":
        "3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "text":
        "Third Edition \n \nPreproduction Draft \n \n David Kirk/NVIDIA and Wen-mei Hwu, 2006-2016 \n20 \nby Thread 2 lag significantly behind their corresponding accesses by Thread 1. The reason \nwhy the bottom is a bad arrangement is that data elements brought back from the DRAM \nneed to be kept in the on-chip memory for a long time, waiting for Thread 2 to consume \nthem. This will likely require a large number of data elements to be kept around, resulting \nin excessive on-chip memory requirements.  \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \n \nFigure 4.13 Tiled Algorithms require synchronization among threads \nIn the context of parallel computing, tiling is a program transformation technique that \nlocalizes the memory locations accessed among threads and the timing of their accesses.  It \nbreaks long access sequences of each thread into phases and use barrier synchronization to \nkeep the timing of accesses to each section by the threads close to each other. It controls the \namount of on-chip memory required by localizing the accesses both in time and in space. In \nterms of our carpool analogy, we keep the threads that form the carpool group to follow \napproximately the same execution timing.  \n \nWe now present a tiled matrix-multiplication algorithm. The basic idea is to have the threads \nto collaboratively load subsets of the M and N elements into the shared memory before they \nindividually use these elements in their dot product calculation. Keep in mind that the size \nof the shared memory is quite small and one must be careful not to exceed the capacity of \nthe shared memory when loading these M and N elements into the shared memory. This can \nbe accomplished by dividing the M and N matrices into smaller tiles. The size of these tiles",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        8,
    "readable_filename":
        "ece408-lecture5-CUDA-tiled-matrix-multiplication-vk-FA23.pdf",
    "s3_path":
        "courses/ECE408FA23/ece408-lecture5-CUDA-tiled-matrix-multiplication-vk-FA23.pdf",
    "text":
        "8\nA Common Programming Strategy\n\nGlobal memory is implemented with DRAM - slow\n\nTo avoid Global Memory bottleneck, tile the input data to take \nadvantage of Shared Memory:\n Partition data into subsets (tiles) that fit into the (smaller but faster) \nshared memory\n Handle each data subset with one thread block by:\n\nLoading the subset from global memory to shared memory, using multiple \nthreads to exploit memory-level parallelism\n\nPerforming the computation on the subset from shared memory; each thread \ncan efficiently access any data element\n\nCopying results from shared memory to global memory\n Tiles are also called blocks in the literature\n David Kirk/NVIDIA and Wen-mei W. Hwu, 2007-2018 \nECE408/CS483/ University of Illinois at Urbana-Champaign",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        34,
    "readable_filename":
        "ece408-lecture5-CUDA-tiled-matrix-multiplication-vk-FA23.pdf",
    "s3_path":
        "courses/ECE408FA23/ece408-lecture5-CUDA-tiled-matrix-multiplication-vk-FA23.pdf",
    "text":
        "Use of Large Tiles Shifts Bottleneck\n Recall our example GPU: 1,000 GFLOP/s, 150 GB/s\n 16x16 tiles use each operand for 16 operations\n reduce global memory accesses by a factor of 16\n 150GB/s bandwidth supports \n(150/4)*16 = 600 GFLOPS!\n 32x32 tiles use each operand for 32 operations\n reduce global memory accesses by a factor of 32\n 150 GB/s bandwidth supports \n(150/4)*32 = 1,200 GFLOPS!\n Memory bandwidth is no longer the bottleneck!\n34\n David Kirk/NVIDIA and Wen-mei W. Hwu, 2007-2018 \nECE408/CS483/ University of Illinois at Urbana-Champaign",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        2,
    "readable_filename":
        "3rd-Edition-Chapter05-performance-FINAL-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter05-performance-FINAL-corrected.pdf",
    "text":
        "Third Edition \n \nPreproduction Draft \n \n David Kirk and Wen-mei Hwu, 2006-2016 \n2 \n \n \nwork; plausible strategies may or may not lead to performance enhancements.  Beyond \ninsights into these resource constraints, this chapter further offers principles and case \nstudies designed to cultivate intuition about the type of algorithm patterns that can result \nin high performance execution. It is also establishes idioms and ideas that will likely lead \nto good performance improvements during your performance tuning efforts. \n \n5.1. Global Memory Bandwidth \n One of the most important factors of CUDA kernel performance is accessing data in the \nglobal memory. CUDA applications exploit massive data parallelism. Naturally, CUDA \napplications tend to process a massive amount of data from the global memory within a \nshort period of time, In Chapter 4, we studied tiling techniques that utilize shared memories \nto reduce the total amount of data that must be accessed from the global memory by a \ncollection of threads in each thread block. In this chapter, we will further discuss memory \ncoalescing techniques that can more effectively move data from the global memory into \nshared memories and registers. Memory coalescing techniques are often used in \nconjunction with tiling techniques to allow CUDA devices to reach their performance \npotential by more efficiently utilizing the global memory bandwidth.1 \n \n                                                 \n1 Recent CUDA devices use on-chip caches for global memory data. Such caches automatically coalesce \nmore of the kernel access patterns and somewhat reduce the need for programmer to manually rearrange \ntheir access patterns. However, even with caches, coalescing techniques will continue to have significant \neffect on kernel execution performance in the foreseeable future. \nWhy are DRAMs so slow? \nThe following figure shows a DRAM cell and the path for accessing its content. The decoder is an electronic \ncircuit that uses a transistor to drive a line connected to the outlet gates of thousands of cells. It can take a \nlong time for the line to be fully charged or discharged to the desired level.  \n \nA more formidable challenge is for the cell to drive the vertical line to the sense amplifiers and allow the \nsense amplifier to detect its content. This is based on electrical charge sharing. The gate lets out the tiny \namount of electrical charge stored in the cell. If the cell content is 1, the tiny amount of charge must raise \nthe electrical potential of the large capacitance of the long bit line to a sufficiently high level that can  \ntrigger the detection mechanism of  the sense amplifier. A good analogy would be for someone to hold a \nsmall cup of coffee at one end of a long hall way for another person to smell the aroma propagated through \nthe hall way to determine the flavor of the coffee. \nOne could speed up the process by using a larger, stronger capacitor in each cell.  However, the DRAMs have \nbeen going in the opposite direction. The capacitors in each cell have been steadily reduced in size and thus \nreduced in their strength over time so that more bits can be stored in each chip. This is why the access \nlatency of DRAMS has not decreased over time.",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        12,
    "readable_filename":
        "ece408-lecture5-CUDA-tiled-matrix-multiplication-vk-FA23.pdf",
    "s3_path":
        "courses/ECE408FA23/ece408-lecture5-CUDA-tiled-matrix-multiplication-vk-FA23.pdf",
    "text":
        "Outline of Technique\n Identify a tile of global data that are accessed by multiple threads\n Load the tile from global memory into on-chip memory\n Have the multiple threads to access their data from the on-chip \nmemory\n Move on to the next block/tile\n12\n David Kirk/NVIDIA and Wen-mei W. Hwu, 2007-2018 \nECE408/CS483/ University of Illinois at Urbana-Champaign",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        33,
    "readable_filename":
        "3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "text":
        "Third Edition \n \nPreproduction Draft \n \n David Kirk/NVIDIA and Wen-mei Hwu, 2006-2016 \n33 \nThe ability to reason about hardware limitations when developing an application is a key \naspect of computational thinking.  \n \nAlthough we introduced tiled algorithms in the context of CUDA programming, it is an \neffective strategy for achieving high-performance in virtually all types of parallel computing \nsystems. The reason is that an application must exhibit locality in data access in order to \nmake effective use of high-speed memories in these systems. For example, in a multi-core \nCPU system, data locality allows an application to effectively use on-chip data caches to \nreduce memory access latency and achieve high performance. Therefore, the reader will find \nthe tiled algorithm useful when he/she develops a parallel application for other types of \nparallel computing systems using other programming models. \n \nOur goal for this chapter is to introduce the concept of locality, tiling, and different CUDA \nmemory types. We introduced a tiled matrix multiplication kernel using shared memory.  We \nhave not discussed the use of registers and constant memory in tiling. We will explain the \nuse of these memory types in tiled algorithms when we discussed parallel algorithm patterns. \n \n4.9. Exercises \n \n1. Consider matrix addition. Can one use shared memory to reduce the global memory \nbandwidth consumption? Hint: analyze the elements accessed by each thread and see if \nthere is any commonality between threads. \n \n2. Draw the equivalent of Figure 4.14 for a 88 matrix multiplication with 22 tiling and \n44 tiling. Verify that the reduction in global memory bandwidth is indeed proportional \nto the dimension size of the tiles. \n \n3. What type of incorrect execution behavior can happen if one forgot to use one or both \n__syncthreads() in the kernel of Figure 4.16? \n \n4. Assuming capacity were not an issue for registers or shared memory, give one important \nreason why it would be valuable to use shared memory instead of registers to hold values \nfetched from global memory?  Explain your answer. \n \n5. For our tiled matrix-matrix multiplication kernel, if we use a 32x32 tile, what is the \nreduction of memory bandwidth usage for input matrices M and N? \n(A) 1/8 of the original usage \n(B) 1/16 of the original usage \n(C) 1/32 of the original usage",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        17,
    "readable_filename":
        "ece408-lecture7-convolution-constant-memory-vk-FA23.pdf",
    "s3_path":
        "courses/ECE408FA23/ece408-lecture7-convolution-constant-memory-vk-FA23.pdf",
    "text":
        "17\nMemory Hierarchies\n Review: If we had to go to global memory to access data all the \ntime, the execution speed of GPUs would be limited by the \nglobal memory bandwidth\n We saw the use of shared memory in tiled matrix multiplication to \nreduce this limitation\n Another important solution: Caches\n David Kirk/NVIDIA and Wen-mei W. Hwu, 2007-2018 \nECE408/CS483/ University of Illinois at Urbana-Champaign",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        1,
    "readable_filename":
        "3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "text":
        "Third Edition \n \nPreproduction Draft \n \n David Kirk/NVIDIA and Wen-mei Hwu, 2006-2016 \n1 \nChapter 4 \nMemory and Data Locality  \n \n \nKeywords: memory bandwidth, memory-bound, on-chip memory, tiling, strip-mining, \nshared memory, private memory, scope, lifetime, occupancy \n \nCHAPTER OUTLINE \n4.1. Importance of Memory Access Efficiency \n4.2. Matrix Multiplication \n4.3. CUDA Memory Types \n4.4. Tiling for Reduced Memory Traffic \n4.5. A Tiled Matrix Multiplication Kernel \n4.6. Boundary Checks \n4.7. Memory as a Limiting Factor to Parallelism \n4.8. Summary \n4.9. Exercises \n \n \nSo far, we have learned how to write a CUDA kernel function and how to configure and \ncoordinate its execution by a massive number of threads. In this chapter, we will begin to \nstudy how one can organize and position the data for efficient access by a massive number \nof threads. We learned in Chapter 2 that the data are first transferred from the host memory \nto the device global memory. In Chapter 3, we studied how to direct the threads to access \ntheir portion of the data from the global memory using their block indexes and thread \nindexes. We have also learned more details about resource assignment and thread \nscheduling. Although this is a very good start, the CUDA kernels that we have learned so \nfar will likely achieve only a tiny fraction of the potential speed of the underlying hardware. \nThe poor performance is due to the fact that global memory, which is typically implemented \nwith DRAM, tends to have long access latencies (hundreds of clock cycles) and finite access \nbandwidth. While having many threads available for execution can theoretically tolerate \nlong memory access latencies, one can easily run into a situation where traffic congestion in \nthe global memory access paths prevents all but very few threads from making progress, \nthus rendering some of the Streaming Multiprocessors (SMs) idle. In order to circumvent \nsuch congestion, CUDA provides a number of additional resources and methods for",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        3,
    "readable_filename":
        "ece408-lecture5-CUDA-tiled-matrix-multiplication-vk-FA23.pdf",
    "s3_path":
        "courses/ECE408FA23/ece408-lecture5-CUDA-tiled-matrix-multiplication-vk-FA23.pdf",
    "text":
        "Objective\n To learn to evaluate the performance implications of global \nmemory accesses\n To prepare for MP3: tiled matrix multiplication\n To learn to assess the benefit of tiling\n3\n David Kirk/NVIDIA and Wen-mei W. Hwu, 2007-2018 \nECE408/CS483/ University of Illinois at Urbana-Champaign",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        16,
    "readable_filename":
        "3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "text":
        "Third Edition \n \nPreproduction Draft \n \n David Kirk/NVIDIA and Wen-mei Hwu, 2006-2016 \n16 \nby tiles (i.e., subsets that each can fit into the shared memory). An important criterion is that \nthe kernel computation on these tiles can be done independently of each other. Note that not \nall data structures can be partitioned into tiles given an arbitrary kernel function.  \n \nThe concept of tiling can be illustrated with the matrix multiplication example. Figure 4.5 \nshows a small example of matrix multiplication. It corresponds to the kernel function in \nFigure 4.3. We replicate the example in Figure 4.9 for convenient reference by the reader. \nFor brevity, we abbreviate P[y*Width+x], M[y*Width+x], and N[y*Width+x] into Py,x, My,x, \nand Ny,x. This example assumes that we use four 22 blocks to compute the P matrix. Figure \n4.5 highlights the computation done by the four threads of block(0,0). These four threads \ncompute P0,0, P0,1, P1,0, and P1,1. The accesses to the M and N elements by thread(0,0) and \nthread(0,1) of block(0,0) are highlighted with black arrows. For example, thread(0,0) reads \nM0,0 and N0,0, followed by M0,1 and N1,0 followed by M0,2 and N2,0, followed by M 0,3 and \nN3,0. \n \n \n \nFigure 4.9 A small example of matrix multiplication. For brevity, We show M[y*Width+x], \nN[y*Width+x], P[y*Width+x] as My,x , Ny,x Py,x. \n \nFigure 4.10 shows the global memory accesses done by all threads in block0,0. The threads \nare listed in the vertical direction, with time of access increasing to the right in the horizontal \ndirection. Note that each thread accesses four elements of M and four elements of N during \nits execution. Among the four threads highlighted, there is a significant overlap in the M and",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        1,
    "readable_filename":
        "ece408-lecture6-dram-tiling-vk-FA23.pdf",
    "s3_path":
        "courses/ECE408FA23/ece408-lecture6-dram-tiling-vk-FA23.pdf",
    "text":
        "ECE408/CS483/CSE408 Fall 2023\nApplied Parallel Programming\nLecture 6: \n Generalized Tiling & \nDRAM Bandwidth\n1\n David Kirk/NVIDIA and Wen-mei W. Hwu, 2007-2018 \nECE408/CS483/ University of Illinois at Urbana-Champaign",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        32,
    "readable_filename":
        "3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "text":
        "Third Edition \n \nPreproduction Draft \n \n David Kirk/NVIDIA and Wen-mei Hwu, 2006-2016 \n32 \n \n  extern __shared__ Mds[]; \n  extern __shared__ Nds[]; \n \nNote that the arrays are now one-dimensional. We will need to use a linearized index based \non the vertical and horizontal indices. \n \nAt run time, when we launch the kernel, we can dynamically determine the amount of shared \nmemory to be used according to the device query result and supply that as a third \nconfiguration parameter to the kernel launch. For example, the revised kernel could be \nlaunched with the following statements: \n \n  size_t size = \n    calculate_appropriate_SM_usage(dev_prop.sharedMemPerBlock,...); \n \n  matrixMulKernel<<<dimGrid, dimBlock, size>>>(Md, Nd, Pd, Width); \n \nwhere size_t is a built-in type for declaring a variable to holds the size information for \ndynamically allocated data structures. The size is expressed in number of bytes. In our matrix \nmultiplication example, for a 16x16 tile, we have size to be 16x16x4=1024 bytes. We have \nomitted the details of the calculation for setting the value of size at run time.  \n4.8. Summary \nIn summary, the execution speed of a program in modern processors can be severely limited \nby the speed of the memory. To achieve good utilization of the execution throughput of \nCUDA devices, one needs to achieve a high compute-to-global-memory-access ratio in the \nkernel code. If the ratio is low, the kernel is memory-bound. That is, its execution speed is \nlimited by the rate at which its operands are accessed from memory. \n \nCUDA defines registers, shared memory, and constant memory. These memories are much \nsmaller than the global memory but can be accessed at much higher speed. Using these \nmemories effectively requires re-design of the algorithm. We use matrix multiplication as \nan example to illustrate tiling, a popular strategy to enhance locality of data access and \nenable effective use of shared memory. In parallel programming, tiling forces multiple \nthreads to jointly focus on a subset of the input data at each phase of the execution so that \nthe subset data can be placed into these special memory types to enable much higher access \nspeed. We demonstrate that with 1616 tiling, global memory accesses are no longer the \nmajor limiting factor for matrix multiplication performance.  \n \nIt is, however, important for CUDA programmers to be aware of the limited sizes of these \ntypes of memory. Their capacities are implementation dependent. Once their capacities are \nexceeded, they limit the number of threads that can be simultaneously executing in each SM.",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        3,
    "readable_filename":
        "ece408-lecture6-dram-tiling-vk-FA23.pdf",
    "s3_path":
        "courses/ECE408FA23/ece408-lecture6-dram-tiling-vk-FA23.pdf",
    "text":
        "Objectives\n To learn to handle boundary conditions in tiled algorithms.\n To understand the organization of memory based on dynamic \nRAM (DRAM).\n To understand the use of burst mode and multiple banks (both \nsources of parallelism) to increase DRAM performance (data rate).\n To understand memory access coalescing, which connects GPU \nkernel performance to DRAM organization. \n3\n David Kirk/NVIDIA and Wen-mei W. Hwu, 2007-2018 \nECE408/CS483/ University of Illinois at Urbana-Champaign",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        29,
    "readable_filename":
        "3rd-Edition-Chapter05-performance-FINAL-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter05-performance-FINAL-corrected.pdf",
    "text":
        "Third Edition \n \nPreproduction Draft \n \n David Kirk and Wen-mei Hwu, 2006-2016 \n29 \n \n \n \n \nFigure 5.17: Increased thread granularity with rectangular tiles \n \nThe potential downside is that the new kernel now uses even more registers and shared \nmemory. As we discussed in the previous section, the number of blocks that can be running \non each SM may decrease. For a given matrix size, tt also reduces the total number of \nthread blocks by half, which may result in insufficient amount of parallelism for matrices \nof smaller dimensions. In practice, combining up to four adjacent horizontal blocks to \ncompute adjacent horizontal tiles significantly improves the performance of large \n(2048x2048 or more) matrix multiplication. \n \n5.6. Summary \nIn this chapter, we reviewed the major aspects of application performance on a CUDA \ndevice: global memory access coalescing, memory parallelism, control flow divergence, \ndynamic resource partitioning and instruction mixes. Each of this aspects is rooted in the \nhardware limitations of the devices. With these insights, the reader should be able to reason \nabout the performance of any kernel code he/she comes across.  \n \nMore importantly, we need to be able to convert poor performing code into well performing \ncode.  As a starting point, we presented practical techniques for creating good program \npatterns for these performance aspects. We will continue to study practical applications of",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        9,
    "readable_filename":
        "ece408-lecture5-CUDA-tiled-matrix-multiplication-vk-FA23.pdf",
    "s3_path":
        "courses/ECE408FA23/ece408-lecture5-CUDA-tiled-matrix-multiplication-vk-FA23.pdf",
    "text":
        "A Common Programming Strategy\n In a GPU, only threads in a block \ncan use shared memory.\n Thus, each block operates on separate tiles:\n Read tile(s) into shared memory using multiple threads to \nexploit memory-level parallelism.\n Compute based on shared memory tiles.\n Repeat.\n Write results back to global memory.\n9\n David Kirk/NVIDIA and Wen-mei W. Hwu, 2007-2018 \nECE408/CS483/ University of Illinois at Urbana-Champaign",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        2,
    "readable_filename":
        "3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "text":
        "Third Edition \n \nPreproduction Draft \n \n David Kirk/NVIDIA and Wen-mei Hwu, 2006-2016 \n2 \naccessing memory that can remove the majority of traffic to and from the global memory. \nIn this chapter, you will learn to use different memory types to boost the execution efficiency \nof CUDA kernels. \n4.1. Importance of Memory Access Efficiency \nWe can illustrate the effect of memory access efficiency by calculating the expected \nperformance level of the most executed portion of the image blur kernel code in Figure 3.8, \nreplicated in Figure 4.1. The most important part of the kernel in terms of execution time is \nthe nested for-loop that performs pixel value accumulation with the blurring patch.  \n \n       for(int blurRow = -BLUR_SIZE; blurRow < BLUR_SIZE+1; ++blurRow) { \n 4.       for(int blurCol = -BLUR_SIZE; blurCol < BLUR_SIZE+1; ++blurCol) { \n \n 5.         int curRow = Row + blurRow; \n 6.         int curCol = Col + blurCol; \n          // Verify we have a valid image pixel \n 7.         if(curRow > -1 && curRow < h && curCol > -1 && curCol < w) { \n 8.           pixVal += in[curRow * w + curCol]; \n 9.           pixels++; // Keep track of number of pixels in the avg \n            } \n          } \n        } \nFigure 4.1: The most executed part of the image blurring kernel in Figure 3.8. \n \nIn every iteration of the inner loop, one global memory access is performed for one floating-\npoint addition. The global memory access fetches an in[] array element. The floating-point \nadd operation accumulates the value of the in[] array element into pixVal. Thus, the ratio of \nfloating-point calculation to global memory access operation is 1 to 1, or 1.0. We will refer \nto this ratio as the compute-to-global-memory-access ratio, defined as the number of \nfloating-point calculations performed for each access to the global memory within a region \nof a program. \n \nThe compute-to-global-memory-access ratio has major implications on the performance of \na CUDA kernel. In a high-end device today, the global memory bandwidth is around 1000 \nGB/s, or 1 TB/s. With four bytes in each single-precision floating-point value, one can expect \nto load no more than 1000/4=250 giga single-precision operands per second. With a \ncompute-to-global-memory ratio of 1.0, the execution of the image blur kernel will be \nlimited by the rate at which the operands (e.g., the elements of in[])can be delivered to the \nGPU. We will refer to programs whose execution speed is limited by memory access \nthroughput as memory bound programs.  In our example, the kernel will achieve no more \nthan 250 giga floating-point operations per second (GFLOPS).",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        4,
    "readable_filename":
        "3rd-Edition-Chapter01-introduction-Final-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter01-introduction-Final-corrected.pdf",
    "text":
        "Chapter 1 \n \n \n4 \ncores and many mega bytes of on-chip cache memories designed to deliver strong \nsequential code performance. \n \nMemory bandwidth is another important issue. The speed of many applications is \nlimited by the rate at which data can be delivered from the memory system into the \nprocessors. Graphics chips have been operating at approximately 10x the memory \nbandwidth of contemporaneously available CPU chips.  A GPU must be capable of \nmoving extremely large amounts of data in and out of its main DRAM (Dynamic \nRandom Access Memory) because of graphics frame buffer requirements and the \nrelaxed memory model (the way various system software, applications, and I/O \ndevices expect how their memory accesses work). In contrast, general-purpose \nprocessors have to satisfy requirements from legacy operating systems, applications \nand I/O devices that make memory bandwidth more difficult to increase.  As a \nresult, we expect that CPUs will continue to be at a disadvantage in terms of \nmemory bandwidth for some time.  \n \n \n \nThe design philosophy of the GPUs has been shaped by the fast growing video \ngame industry that exerts tremendous economic pressure for the ability to perform \na massive number of floating-point calculations per video frame in advanced \ngames.  This demand motivates GPU vendors to look for ways to maximize the \nchip area and power budget dedicated to floating-point calculations. An important \nobservation is that reducing latency is much more expensive than increasing \nthroughput in terms of power and chip area. Therefore, the prevailing solution is to \noptimize for the execution throughput of massive numbers of threads. The design \nsaves chip area and power by allowing pipelined memory channels and arithmetic \noperations to have long latency. The reduced area and power of the memory access",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        23,
    "readable_filename":
        "3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "text":
        "Third Edition \n \nPreproduction Draft \n \n David Kirk/NVIDIA and Wen-mei Hwu, 2006-2016 \n23 \nopportunity to use small, high-speed memories to serve most of the accesses and remove \nthese accesses from the global memory. Locality is as important for achieving high-\nperformance in multi-core CPUs as in many-thread GPUs We will return to the concept of \nlocality in Chapter 5. \n \n4.5. A Tiled Matrix Multiplication Kernel \nWe are now ready to present a tiled matrix multiplication kernel that uses shared memory to \nreduce traffic to the global memory. The kernel shown in Figure 4.16 implements the phases \nillustrated in Figure 4.15.  In Figure 4.16, Line 1 and Line 2 declare Mds and Nds as shared \nmemory variables. Recall that the scope of shared memory variables is a block. Thus, one \npair of Mds and Nds will be created for each block and all threads of a block have access to \nthe same Mds and Nds. This is important since all threads in a block must have access to the \nM and N elements loaded into Mds and Nds by their peers so that they can use these values \nto satisfy their input needs. \n \n#define TILE_WIDTH 16 \n \n    __global__ void MatrixMulKernel(float* M, float* N, float* P, \n      int Width) { \n   \n 1.   __shared__ float Mds[TILE_WIDTH][TILE_WIDTH]; \n 2.   __shared__ float Nds[TILE_WIDTH][TILE_WIDTH]; \n \n 3.   int bx = blockIdx.x;  int by = blockIdx.y; \n 4.   int tx = threadIdx.x; int ty = threadIdx.y; \n \n      // Identify the row and column of the P element to work on \n 5.   int Row = by * TILE_WIDTH + ty; \n 6.   int Col = bx * TILE_WIDTH + tx; \n \n 7.   float Pvalue = 0; \n      // Loop over the M and N tiles required to compute P element \n 8.   for (int ph = 0; ph < Width/TILE_WIDTH; ++ph) { \n \n        // Collaborative loading of M and N tiles into shared memory \n 9.     Mds[ty][tx] = M[Row*Width + ph*TILE_WIDTH + tx]; \n10.     Nds[ty][tx] = N[(ph*TILE_WIDTH + ty)*Width + Col]; \n11.     __syncthreads(); \n \n12.     for (int k = 0; k < TILE_WIDTH; ++k) { \n13.       Pvalue += Mds[ty][k] * Nds[k][tx]; \n        } \n14.     __syncthreads(); \n      } \n15.   P[Row*Width + Col] = Pvalue;",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        11,
    "readable_filename":
        "3rd-Edition-Chapter05-performance-FINAL-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter05-performance-FINAL-corrected.pdf",
    "text":
        "Third Edition \n \nPreproduction Draft \n \n David Kirk and Wen-mei Hwu, 2006-2016 \n11 \n \n \n \nLines 5, 6, 9, 10 in Figure 5.6 form a frequently used programming pattern for loading \nmatrix elements into shared memory in tiled algorithms. We would also like to encourage \nthe reader to analyze the data access pattern by the dot-product loop in lines 12 and 13. \nNote that the threads in a warp do not access consecutive location of Mds. This is not a \nproblem since Mds is in shared memory, which does not require coalescing to achieve high \nspeed data access.  \n5.2. More on Memory Parallelism \nAs we explained in Section 5.1, DRAM bursting is a form of parallel organization: multiple \nlocations around are accessed in the DRAM core array in parallel. Modern However, \nbursting alone is not sufficient to realize the level of DRAM access bandwidth required by \nmodern processors. DRAM systems typically employ two more forms of parallel \norganization  banks and channels. At the highest level, a processor contains one or more \nchannels. Each channel is a memory controller with a bus that connects a set of DRAM \nbanks to the processor. Figure 5.7 illustrates a processor that contains four channels, each \nwith a bus that connects four DRAM banks to the processor. In real systems, a processor \ntypically have one to eight channels and each channel is connected a large number of banks. \n \n \nFigure 5.7: Channels and banks in DRAM systems \n \nThe data transfer bandwidth of a bus is defined by its width and clock frequency. Modern \ndouble data rate (DDR) busses perform two data transfers per clock cycle, one at the rising \nedge and one at the falling edge of each clock cycle. For example, a 64-bit DDR bus with \na clock frequency of 1 GHz has a bandwidth of 8B * 2 * 1GHz = 16GB/sec. This seems to \nbe a large number but is often too small for modern CPUs and GPUs. A modern CPU might \nrequire a memory bandwidth of at least 32 GB/sec whereas a modern GPU might require \n128 GB/s. For this example, the CPU would require 2 channels and the GPU would require \n8 channels.",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        7,
    "readable_filename":
        "ece408-lecture5-CUDA-tiled-matrix-multiplication-vk-FA23.pdf",
    "s3_path":
        "courses/ECE408FA23/ece408-lecture5-CUDA-tiled-matrix-multiplication-vk-FA23.pdf",
    "text":
        "7\nGrid\nGlobal Memory\nBlock (0, 0)\nShared Memory\nThread (0, 0)\nRegisters\nThread (1, 0)\nRegisters\nBlock (1, 0)\nShared Memory\nThread (0, 0)\nRegisters\nThread (1, 0)\nRegisters\nHost\nConstant Memory\nHow about performance on a device with \n150 GB/s memory bandwidth?\n All threads access global memory for \ntheir input matrix elements\n\nTwo memory accesses (8 bytes) per \nfloating point multiply-add (2 fp ops)\n\n4B/s of memory bandwidth/FLOPS\n\n150 GB/s limits the code at 37.5 GFLOPS\n The actual code runs at about 25 \nGFLOPS\n Need to drastically cut down memory \naccesses to get closer to the peak of \nmore than 1,000 GFLOPS\n David Kirk/NVIDIA and Wen-mei W. Hwu, 2007-2018 \nECE408/CS483/ University of Illinois at Urbana-Champaign",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        28,
    "readable_filename":
        "ece408-lecture4-CUDA-memory-model-vk-FA23.pdf",
    "s3_path":
        "courses/ECE408FA23/ece408-lecture4-CUDA-memory-model-vk-FA23.pdf",
    "text":
        "28\nGrid\nGlobal Memory\nBlock (0, 0)\nShared Memory\nThread (0, 0)\nRegisters\nThread (1, 0)\nRegisters\nBlock (1, 0)\nShared Memory\nThread (0, 0)\nRegisters\nThread (1, 0)\nRegisters\nHost\nConstant Memory\n150 GB/s Bandwidth Implies 37.5 GFLOPs\n One generation of GPUs:\n1,000 GFLOP/s of compute power, \nand\n150 GB/s of memory bandwidth.\n Dividing bandwidth by memory \nrequirements:\n /\n / = 37.5 GFLOP/s\n  which limits computation!\n David Kirk/NVIDIA and Wen-mei W. Hwu, 2007-2018 \nECE408/CS483/ University of Illinois at Urbana-Champaign",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        17,
    "readable_filename":
        "3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "text":
        "Third Edition \n \nPreproduction Draft \n \n David Kirk/NVIDIA and Wen-mei Hwu, 2006-2016 \n17 \nN elements they access. For example, thread0,0 and thread0,1 both access M0,0 as well as the \nrest of row 0 of M. Similarly, thread0,1 and thread1,1 both access N0,1 as well as the rest of \ncolumn 1 of N. \n \nThe kernel in Figure 4.3 is written so that both thread0,0 and thread0,1 access row 0 elements \nof M from the global memory. If we can somehow manage to have thread0,0 and thread1,0 to \ncollaborate so that these M elements are only loaded from global memory once, we can \nreduce the total number of accesses to the global memory by half. In fact, we can see that \nevery M and N element is accessed exactly twice during the execution of block0,0. Therefore, \nif we can have all four threads to collaborate in their accesses to global memory, we can \nreduce the traffic to the global memory by half. \n \nReaders should verify that the potential reduction in global memory traffic in the matrix \nmultiplication example is proportional to the dimension of the blocks used. With \nWidthWidth blocks, the potential reduction of global memory traffic would be Width. That \nis, if we use 1616 blocks, one can potentially reduce the global memory traffic to 1/16 \nthrough collaboration between threads. \n \n \n \nFigure 4.10: Global memory accesses performed by threads in block0,0 \n \nTraffic congestion obviously does not only arise in computing. Most of us have experienced \ntraffic congestion in highway systems, as illustrated in Figure 4.11. The root cause of \nhighway traffic congestion is that there are too many cars all squeezing through a road that \nis designed for a much smaller number of vehicles. When congestion occurs, the travel time \nfor each vehicle is greatly increased. Commute time to work can easily double or triple \nduring traffic congestion.",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        11,
    "readable_filename":
        "3rd-Edition-Chapter07-convolution-FINAL-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter07-convolution-FINAL-corrected.pdf",
    "text":
        "Third Edition \n \nPreproduction Draft \n David Kirk/NVIDIA and Wen-mei Hwu, 2006-2016 \n11 \na copy of the variable is available in cache. The value of the variable will then be provided \nfrom the cache, eliminating the need to access DRAM.  \n \nThere is a tradeoff between the size of a memory and the speed of a memory. As a result, \nmodern processors often employ multiple levels of caches. The numbering convention for \nthese cache levels reflects the distance to the processor. The lowest level, L1 or Level 1, is \nthe cache that is directly attached to a processor core. It runs at a speed very close to the \nprocessor in both latency and bandwidth. However, an L1 cache is small in size, typically \nbetween 16KB and 64KB. L2 caches are larger, in the range of 128KB to 1MB, but can take \ntens of cycles to access. They are typically shared among multiple processor cores, or SMs \nin a CUDA device. In some high-end processors today, there are even L3 caches that can be \nof several MB in size.  \n \nA major design issue with using caches in a massively parallel processor is cache coherence, \nwhich arises when one or more processor cores modify cached data. Since L1 caches are \ntypically directly attached to only one of the processor cores, changes in its contents are not \neasily observed by other processor cores. This causes a problem if the modified variable is \nshared among threads running on different processor cores. A cache coherence mechanism \nis needed to ensure that the contents of the caches of the other processor cores are updated. \nCache coherence is difficult and expensive to provide in massively parallel processors. \nHowever, their presence typically simplifies parallel software development. Therefore, \nmodern CPUs typically support cache coherence among processor cores. While modern \nGPUs provide two levels of caches, they typically do without cache coherence to maximize \nhardware resources available to increase the arithmetic throughput of the processor. \n \nConstant memory variables play an interesting role in using caches in massively parallel \nprocessors. Since they are not changed during kernel execution, there is no cache coherence \nissue during the execution of a kernel. Therefore, the hardware can aggressively cache the \nconstant variable values in L1 caches. Furthermore, the design of caches in these processors \nis typically optimized to broadcast a value to a large number of threads. As a result, when \nall threads in a warp access the same constant memory variable, as is the case of M, the \ncaches can provide tremendous amount of bandwidth to satisfy the data needs of threads. \nAlso, since the size of M is typically small, we can assume that all M elements are effectively \nalways accessed from caches. Therefore, we can simply assume that no DRAM bandwidth \nis spent on M accesses. With the use of constant memory and caching, we have effectively \ndoubled the ratio of floating-point arithmetic to memory access to 2. \n \nAs it turns out, the accesses to the input N array elements can also benefit from caching in \nmore recent GPUs. We will come back to this point in Section 7.5.  \n7.4. Tiled 1D Convolution with Halo Cells \nWe will now address the memory bandwidth issue in accessing N array element with a tiled \nconvolution algorithm. Recall that in a tiled algorithm, threads collaborate to load input",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        14,
    "readable_filename":
        "ece408-lecture8-tiled-convolution-vk-FA23.pdf",
    "s3_path":
        "courses/ECE408FA23/ece408-lecture8-tiled-convolution-vk-FA23.pdf",
    "text":
        "Three Tiling Strategies\n14\nOutput\nInput\nStrategy 1\n1. Block size covers output tile\n2. Use multiple steps to load input tile\nStep 1\nStep 2\nStep 3\nOutput\nInput\nStrategy 2\n1. Block size covers input tile\n2. Load input tile in one step\n3. Turn off some threads when calculating  output\nOutput\nInput\nAccess\nfrom \nglobal \nmem\nshared memory\nAccess\nfrom \nglobal \nmem\nStrategy 3\n1. Block size covers output tile\n2. Load only core of input tile\n3. Access halo cells from global memory\n David Kirk/NVIDIA and Wen-mei W. Hwu, 2007-2018 \nECE408/CS483/ University of Illinois at Urbana-Champaign",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        57,
    "readable_filename":
        "CUDA_C_Best_Practices_Guide.pdf",
    "s3_path":
        "courses/ECE408FA23/CUDA_C_Best_Practices_Guide.pdf",
    "text":
        "CUDA C++ Best Practices Guide, Release 12.2\nFig. 10: The performance of the sliding-window benchmark with tuned hit-ratio\n13.2.3. Shared Memory\nBecause it is on-chip, shared memory has much higher bandwidth and lower latency than local and\nglobal memory - provided there are no bank conflicts between the threads, as detailed in the following\nsection.\n13.2.3.1 Shared Memory and Memory Banks\nTo achieve high memory bandwidth for concurrent accesses, shared memory is divided into equally\nsized memory modules (banks) that can be accessed simultaneously. Therefore, any memory load or\nstore of n addresses that spans n distinct memory banks can be serviced simultaneously, yielding an\neffective bandwidth that is n times as high as the bandwidth of a single bank.\nHowever, if multiple addresses of a memory request map to the same memory bank, the accesses\nare serialized. The hardware splits a memory request that has bank conflicts into as many separate\nconflict-free requests as necessary, decreasing the effective bandwidth by a factor equal to the num-\nber of separate memory requests. The one exception here is when multiple threads in a warp address\nthe same shared memory location, resulting in a broadcast. In this case, multiple broadcasts from\ndifferent banks are coalesced into a single multicast from the requested shared memory locations to\nthe threads.\nTo minimize bank conflicts, it is important to understand how memory addresses map to memory\nbanks and how to optimally schedule memory requests.\nOn devices of compute capability 5.x or newer, each bank has a bandwidth of 32 bits every clock cycle,\nand successive 32-bit words are assigned to successive banks. The warp size is 32 threads and the\nnumber of banks is also 32, so bank conflicts can occur between any threads in the warp. See Compute\nCapability 5.x in the CUDA C++ Programming Guide for further details.\n13.2. Device Memory Spaces\n51",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        21,
    "readable_filename":
        "3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "text":
        "Third Edition \n \nPreproduction Draft \n \n David Kirk/NVIDIA and Wen-mei Hwu, 2006-2016 \n21 \nis chosen so that they can fit into the shared memory. In the simplest form, the tile \ndimensions equal those of the block, as illustrated in Figure 4.11.  \n \n \n \nFigure 4.14 Tiling M and N to utilize shared memory \n \nIn Figure 4.14, we divide M and N into 22 tiles, as delineated by the thick lines. The dot \nproduct calculations performed by each thread are now divided into phases. In each phase, \nall threads in a block collaborate to load a tile of M and a tile of N into the shared memory. \nThis can be done by having every thread in a block to load one M element and one N element \ninto the shared memory, as illustrated in Figure 4.15. Each row of Figure 4.15 shows the \nexecution activities of a thread. Note that time progresses from left to right. We only need \nto show the activities of threads in block0,0; the other blocks all have the same behavior. The \nshared memory array for the M elements is called Mds. The shared memory array for the N \nelements is called Nds. At the beginning of Phase 1, the four threads of block0,0 \ncollaboratively load a tile of M into shared memory: thread0,0  loads M0,0 into Mds0,0, thread0,1 \nloads M0,1 into Mds0,1, thread1,0 loads M1,0 into Mds1,0, and thread1,1 loads M1,1 into Mds1,1. \nThese loads are shown in the second column of Figure 4.15. A tile of N is also loaded in a \nsimilar manner, shown in the third column of Figure 4.15. \n \nAfter the two tiles of M and N are loaded into the shared memory, these elements are used \nin the calculation of the dot product. Note that each value in the shared memory is used \ntwice. For example, the M1,1 value, loaded by thread1,1 into Mds1,1, is used twice, once by \nthread1,0 and once by thread1,1. By loading each global memory value into shared memory",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        15,
    "readable_filename":
        "3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "text":
        "Third Edition \n \nPreproduction Draft \n \n David Kirk/NVIDIA and Wen-mei Hwu, 2006-2016 \n15 \n__device__ in front of __constant__ to achieve the same effect. Declaration of constant \nvariables must be outside any function body. The scope of a constant variable is all grids, \nmeaning that all threads in all grids see the same version of a constant variable. The lifetime \nof a constant variable is the entire application execution. Constant variables are often used \nfor variables that provide input values to kernel functions. Constant variables are stored in \nthe global memory but are cached for efficient access. With appropriate access patterns, \naccessing constant memory is extremely fast and parallel. Currently, the total size of constant \nvariables in an application is limited at 65,536 bytes. One may need to break up the input \ndata volume to fit within this limitation, as we will illustrate in Chapter 7. \n \nA variable whose declaration is preceded only by the keyword __device__ (each __ \nconsists of two _ characters), is a global variable and will be placed in the global memory. \nAccesses to a global variable are slow. Latency and throughput of accessing global variables \nhave been improved with caches in more recent devices.  One important advantage of global \nvariables is that they are visible to all threads of all kernels. Their contents also persist \nthrough the entire execution. Thus, global variables can be used as a means for threads to \ncollaborate across blocks. One must, however, be aware of the fact that there is currently no \neasy way to synchronize between threads from different thread blocks or to ensure data \nconsistency across threads when accessing global memory other than terminating the current \nkernel execution3.  Therefore, global variables are often used to pass information from one \nkernel invocation to another kernel invocation.  \n \nIn CUDA, pointers are used to point to data objects in the global memory. There are two \ntypical ways in which pointer usage arises in kernel and device functions. First, if an object \nis allocated by a host function, the pointer to the object is initialized by cudaMalloc and can \nbe passed to the kernel function as a parameter. For example, the parameters M, N, and P in \nFigure 4.1 are such pointers. The second type of usage is to assign the address of a variable \ndeclared in the global memory to a pointer variable. For example, the statement {float* ptr = \n&GlobalVar;} in a kernel function assigns the address of GlobalVar into an automatic pointer \nvariable ptr. The reader should refer to the CUDA Programming Guide for using pointers in other \nmemory types. \n4.4. Tiling for Reduced Memory Traffic \nWe have an intrinsic tradeoff in the use of device memories in CUDA: the global memory \nis large but slow whereas the shared memory is small but fast. A common strategy is to \npartition the data into subsets called tiles so that each tile fits into the shared memory. The \nterm tile draws on the analogy that a large wall (i.e., the global memory data) can be covered \n                                                 \n3 Note that one can use CUDA memory fencing to ensure data coherence between thread blocks if the \nnumber of thread blocks is smaller than the number of SMs in the CUDA device. See the CUDA \nprogramming guide for more details.",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        24,
    "readable_filename":
        "3rd-Edition-Chapter07-convolution-FINAL-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter07-convolution-FINAL-corrected.pdf",
    "text":
        "Third Edition \n \nPreproduction Draft \n David Kirk/NVIDIA and Wen-mei Hwu, 2006-2016 \n24 \nThe larger the ratio is, the more effective the tiled algorithm is in reducing the number of \nmemory accesses as compared to the basic algorithm. \n \n \nFigure 7.22 Image array access reduction ratio for different tile sizes. \n \nFigure 7.22 shows the trend of the image array access reduction ratio as we vary \nO_TILE_WIDTH, the output tile size. As O_TILE_WIDTH becomes very large, the size of \nthe mask becomes negligible compared to tile size. Thus, each input element loaded will be \nused about (Mask_Width)2 times. For Mask_Width value of 5, we expect that the ratio will \napproach 25 as the O_TILE_WIDTH becomes much larger than 5. For example, for \nO_TILE_WIDTH = 64, the ratio is 22.1. This is significantly higher than the ratio of 11.1 for \nO_TILE_WIDTH = 8. The important takeaway point is that we must have a sufficiently large \nO_TILE_WIDTH in order for the tiled kernel to deliver its potential benefit. The cost of a large \nO_TILE_WIDTH is the amount of shared memory needed to hold the input tiles. \n \nFor a larger Mask_Width, such as 9 in the bottom row of Figure 7.22, the ideal ratio should \nbe 92= 81. However, even with a large O_TILE_WIDTH such as 64, the ratio is only 64. Note \nthat O_TILE_WIDTH=64 and Mask_Width=9 translate into input tile size of 722=5184 \nelements or 20,736 bytes assuming single precision data. This is more than the about the \namount of available shared memory in each SM of the current generation of GPUs. Stencil \ncomputation that is derived from finite difference methods for solving differential equation \noften require a Mask_Width of 9 or above to achieve numerical stability. Such stencil \ncomputation can benefit from larger amount of shared memory in future generations of \nGPUs. \n \n7.7. Summary \nIn this chapter, we have studied convolution as an important parallel computation pattern. \nWhile convolution is used in many applications such as computer vision and video \nprocessing, it is also represents a general pattern that forms the basis of many parallel \nalgorithms. For example one can view the stencil algorithms in partial differential equation \n(PDE) solvers as a special case of convolution. For another example, one can also view the \ncalculation of grid point force or potential value as a special case of convolution.  \n \nWe have presented a basic parallel convolution algorithm whose implementations will be \nlimited by DRAM bandwidth for accessing both the input N and mask M elements. We then",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        8,
    "readable_filename":
        "3rd-Edition-Chapter01-introduction-Final-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter01-introduction-Final-corrected.pdf",
    "text":
        "Chapter 1 \n \n \n8 \ninstruction cache.  Each GPU currently comes with gigabytes of GDDR (Graphics \nDouble Data Rate) SDRAM (Synchronous DRAM), referred to as Global Memory \nin Figure 1.2. These GDDR SDRAMs differ from the system DRAMs on the CPU \nmotherboard in that they are essentially the frame buffer memory that is used for \ngraphics. For graphics applications, they hold video images and texture information \nfor 3D rendering. For computing, they function as very high bandwidth off-chip \nmemory, though with somewhat longer latency than typical system memory.  For \nmassively parallel applications, the higher bandwidth makes up for the longer \nlatency. More recent product such as NVIDIAs Pascal architecture, may use HBM \n(High-Bandwidth Memory) or HBM2 architecture.  For brevity, we will simply \nrefer to all of these types of memory as DRAM for the rest of the book. \n \n \nThe G80 introduced the CUDA architecture and had a communication link to the \nCPU core logic over a PCI-Express Generation 2 (Gen2) interface.  Over PCI-E \nGen2, a CUDA application can transfer data from the system memory to the global \nmemory at 4 GB/S, and at the same time upload data back to the system memory \nat 4 GB/S. Altogether, there is a combined total of 8 GB/S.  More recent GPUs use \nPCI-E Gen3 or Gen4, which supports 8-16 GB/s in each direction. The Pascal \nfamily of GPUs also supports NVLINK, a CPU-GPU and GPU-GPU interconnect \nthat allows transfers of up to 40GB/s per channel.  As the size of GPU memory \ngrows, applications increasingly keep their data in the global memory and only \noccasionally use the PCI-E or NVLINK to communicate with the CPU system \nmemory if there is need for using a library that is only available on the CPUs.   The \ncommunication bandwidth is also expected to grow as the CPU bus bandwidth of \nthe system memory grows in the future.",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        13,
    "readable_filename":
        "3rd-Edition-Chapter11-merge-FINAL-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter11-merge-FINAL-corrected.pdf",
    "text":
        "Third Edition \n \nPreproduction Draft \n David Kirk/NVIDIA and Wen-mei Hwu, 2006-2016 \n13 \n \nWhile the basic merge kernel is quite simple and elegant, it falls short in memory access \nefficiency.  First, it is be clear that when executing the merge_sequential function, adjacent \nthreads in a warp are not accessing adjacent memory locations when they read and write the \ninput and output subarray elements. For the example in Figure 11.9, during the first iteration \nof the merge_sequential function execution, the three adjacent threads would read A[0], A[2], \nand B[0]. They will then write to C[0], C[3], and C[6]. Thus, their memory accesses are not \ncoalesced, resulting in poor utilization of memory bandwidth.  \n \nSecond, the threads also need to access A and B elements from the global memory when they \nexecute the co-rank function. Since we are doing a binary search, the access patterns are \nsomewhat irregular and will unlikely be coalesced. As a result, these accesses can further \nreduce the efficiency of utilizing the memory bandwidth. It would be helpful if we can \nreduce the number accesses to the global memory by the co-rank function. \n \n11.6. A Tiled Merge Kernel \nAs we have seen in Chapter 4, we can use shared memory to change the memory access \npatterns of the merge kernel into ones that can be coalesced. The key observation is that the \ninput A and B subarrays to be used by the adjacent threads are adjacent to each other in \nmemory.  Essentially, all threads in a block will collective use larger, block-level subarrays \nof A and B to generate a lager, block-level subarray of C. We can call the co-rank function \nfor the entire block to get the starting and ending locations for the block-level A and B \nsubarrays. Using these block-level co-rank values, all threads in the block can cooperatively \nload the elements of the block-level A and B subarrays into the shared memory in a coalesced \npattern. \n \n \nFigure 11.11: Design of a tiled merge kernel",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        43,
    "readable_filename":
        "CUDA_C_Best_Practices_Guide.pdf",
    "s3_path":
        "courses/ECE408FA23/CUDA_C_Best_Practices_Guide.pdf",
    "text":
        "Chapter 13. Memory Optimizations\nMemory optimizations are the most important area for performance. The goal is to maximize the use\nof the hardware by maximizing bandwidth. Bandwidth is best served by using as much fast memory\nand as little slow-access memory as possible. This chapter discusses the various kinds of memory on\nthe host and device and how best to set up data items to use the memory effectively.\n13.1. Data Transfer Between Host and Device\nThe peak theoretical bandwidth between the device memory and the GPU is much higher (898 GB/s\non the NVIDIA Tesla V100, for example) than the peak theoretical bandwidth between host memory\nand device memory (16 GB/s on the PCIe x16 Gen3). Hence, for best overall application performance,\nit is important to minimize data transfer between the host and the device, even if that means running\nkernels on the GPU that do not demonstrate any speedup compared with running them on the host\nCPU.\nNote: High Priority: Minimize data transfer between the host and the device, even if it means running\nsome kernels on the device that do not show performance gains when compared with running them\non the host CPU.\nIntermediate data structures should be created in device memory, operated on by the device, and\ndestroyed without ever being mapped by the host or copied to host memory.\nAlso, because of the overhead associated with each transfer, batching many small transfers into one\nlarger transfer performs significantly better than making each transfer separately, even if doing so\nrequires packing non-contiguous regions of memory into a contiguous buffer and then unpacking\nafter the transfer.\nFinally, higher bandwidth between the host and the device is achieved when using page-locked (or\npinned) memory, as discussed in the CUDA C++ Programming Guide and the Pinned Memory section\nof this document.\n37",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        26,
    "readable_filename":
        "3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "text":
        "Third Edition \n \nPreproduction Draft \n \n David Kirk/NVIDIA and Wen-mei Hwu, 2006-2016 \n26 \nusing the M and N elements in the shared memory before any of them move on to the next \niteration and load the elements from the next tiles. This way, none of the threads would load \nthe elements too early and corrupt the input values for other threads. \n \nThe nested loop from Line 8 to Line 14 illustrates a technique called strip-mining, which \ntakes a long-running loop and break it into phases. Each phase consists of an inner loop that \nexecutes a number of consecutive iterations of the original loop. The original loop becomes \nan outer loop whose role is to iteratively invoke the inner loop so that all the iterations of the \noriginal loop are executed in their original order. By adding barrier synchronizations before \nand after the inner loop, we force all threads in the same block to all focus their work on a \nsection of their input data. Strip-mining is an important means to creating the phases needed \nby tiling in data parallel programs. 4 \n \nAfter all phases of the dot product are complete, the execution exits the loop of Line 8. All \nthreads write to their P element using the linearized index calculated from Row and Col. \n \nThe benefit of the tiled algorithm is substantial. For matrix multiplication, the global memory \naccesses are reduced by a factor of TILE_WIDTH. If one uses 1616 tiles, we can reduce \nthe global memory accesses by a factor of 16. This increases the compute-to-global-memory-\naccess ratio from 1 to 16. This improvement allows the memory bandwidth of a CUDA \ndevice to support a computation rate close to its peak performance. For example, this \nimprovement allows a device with 150 GB/s global memory bandwidth to approach \n((150/4)*16) = 600 GFLOPS! \n \nWhile the performance improvement of the tiled matrix multiplication kernel is impressive, \nit does make a few simplifying assumptions. First, the width of the matrices are assumed to \nbe a multiple of the width of thread blocks. This prevents the kernel from correctly \nprocessing arbitrary sized matrices. The second assumption is that the matrices are square \nmatrices. This is not always true in practice. In the next section, we will present a kernel \nwith boundary checks that removes these assumptions. \n \n4.6. Boundary Checks \nWe now extend the tiled matrix multiplication kernel to handle matrices with arbitrary width. \nThe extensions will have to allow the kernel to correctly handle matrices whose width is not \n                                                 \n4 Interested reader should note that strip-mining has long been used in programming CPUs. Strip-mining \nfollowed by loop interchange is often used to enable tiling for improved locality in sequential programs. \nStrip-mining is also the main vehicle for vectorizing compilers to generate vector or SIMD instructions for \nCPU programs.",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        19,
    "readable_filename":
        "3rd-Edition-Chapter07-convolution-FINAL-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter07-convolution-FINAL-corrected.pdf",
    "text":
        "Third Edition \n \nPreproduction Draft \n David Kirk/NVIDIA and Wen-mei Hwu, 2006-2016 \n19 \nthe shared memory. Otherwise, it is accessed from the N array, which is hopefully in the L2 \ncache.  The complete 1D tiled convolution kernel with caching is shown in Figure 7.14. \n \n \nFigure 7.14 A simpler tiled 1D convolution kernel using constant memory and general \ncaching. \n7.6. Tiled 2D Convolution with Halo Cells \nNow that we have learned how to tile a parallel 1D convolution computation, we can extend \nour knowledge to 2D quite easily. For a little more fun, we will use an example based on a \nclass of 2D image format that is frequently encountered in image libraries and applications. \n \nAs we have seen in Chapter 3, real-world images are represented as 2D matrices and come \nin all sizes and shapes. Image processing libraries typically store these images in row-major \nlayout when reading them from files into memory. If the width of the image in terms of bytes \nis not a multiple of the DRAM burst size, the starting point of row 1 and beyond can be \nmisaligned from the DRAM burst boundaries. As we have seen in Chapter 5, such \nmisalignment can result in poor utilization of DRAM bandwidth when we attempt to access \ndata in one of the rows. As a result, image libraries often also convert images into a padded \nformat when reading them from files into memory, as illustrated in Figure 7.15. \n \n__global__ void convolution_1D_tiled_caching_kernel(float *N, float *P, int \nMask_Width, \n  int Width) { \n  int i = blockIdx.x*blockDim.x + threadIdx.x; \n  __shared__ float  N_ds[TILE_SIZE]; \n  N_ds[threadIdx.x] = N[i]; \n  __syncthreads(); \n  int This_tile_start_point = blockIdx.x * blockDim.x; \n  int Next_tile_start_point = (blockIdx.x + 1) * blockDim.x; \n  int N_start_point = i - (Mask_Width/2); \n  float Pvalue = 0; \n  for (int j = 0; j < Mask_Width; j ++) { \n     int N_index = N_start_point + j; \n     if (N_index >= 0  && N_index < Width) { \n       if ((N_index >= This_tile_start_point) \n         && (N_index < Next_tile_start_point)) { \n         Pvalue += N_ds[threadIdx.x+j-(Mask_Width/2)]*M[j]; \n       } else { \n         Pvalue += N[N_index] * M[j]; \n       } \n     } \n  } \n  P[i] = Pvalue; \n}",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        158,
    "readable_filename":
        "CUDA_C_Programming_Guide.pdf",
    "s3_path":
        "courses/ECE408FA23/CUDA_C_Programming_Guide.pdf",
    "text":
        "CUDA C++ Programming Guide, Release 12.2\nTo achieve high bandwidth, shared memory is divided into equally-sized memory modules, called banks,\nwhich can be accessed simultaneously. Any memory read or write request made of n addresses that\nfall in n distinct memory banks can therefore be serviced simultaneously, yielding an overall bandwidth\nthat is n times as high as the bandwidth of a single module.\nHowever, if two addresses of a memory request fall in the same memory bank, there is a bank conflict\nand the access has to be serialized. The hardware splits a memory request with bank conflicts into\nas many separate conflict-free requests as necessary, decreasing throughput by a factor equal to the\nnumber of separate memory requests. If the number of separate memory requests is n, the initial\nmemory request is said to cause n-way bank conflicts.\nTo get maximum performance, it is therefore important to understand how memory addresses map\nto memory banks in order to schedule the memory requests so as to minimize bank conflicts. This\nis described in Compute Capability 5.x, Compute Capability 6.x, Compute Capability 7.x, Compute Ca-\npability 8.x, and Compute Capability 9.0 for devices of compute capability 5.x, 6.x, 7.x, 8.x, and 9.0\nrespectively.\nConstant Memory\nThe constant memory space resides in device memory and is cached in the constant cache.\nA request is then split into as many separate requests as there are different memory addresses in the\ninitial request, decreasing throughput by a factor equal to the number of separate requests.\nThe resulting requests are then serviced at the throughput of the constant cache in case of a cache\nhit, or at the throughput of device memory otherwise.\nTexture and Surface Memory\nThe texture and surface memory spaces reside in device memory and are cached in texture cache, so\na texture fetch or surface read costs one memory read from device memory only on a cache miss,\notherwise it just costs one read from texture cache. The texture cache is optimized for 2D spatial\nlocality, so threads of the same warp that read texture or surface addresses that are close together in\n2D will achieve best performance. Also, it is designed for streaming fetches with a constant latency;\na cache hit reduces DRAM bandwidth demand but not fetch latency.\nReading device memory through texture or surface fetching present some benefits that can make it\nan advantageous alternative to reading device memory from global or constant memory:\n If the memory reads do not follow the access patterns that global or constant memory reads\nmust follow to get good performance, higher bandwidth can be achieved providing that there is\nlocality in the texture fetches or surface reads;\n Addressing calculations are performed outside the kernel by dedicated units;\n Packed data may be broadcast to separate variables in a single operation;\n 8-bit and 16-bit integer input data may be optionally converted to 32 bit floating-point values in\nthe range [0.0, 1.0] or [-1.0, 1.0] (see Texture Memory).\n142\nChapter 8. Performance Guidelines",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        23,
    "readable_filename":
        "ece408-lecture6-dram-tiling-vk-FA23.pdf",
    "s3_path":
        "courses/ECE408FA23/ece408-lecture6-dram-tiling-vk-FA23.pdf",
    "text":
        "Global Memory (DRAM) Bandwidth\nIdeal\n \nReality\n23\n David Kirk/NVIDIA and Wen-mei W. Hwu, 2007-2018 \nECE408/CS483/ University of Illinois at Urbana-Champaign",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        9,
    "readable_filename":
        "3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter04-memory-model-FINAL-corrected.pdf",
    "text":
        "Third Edition \n \nPreproduction Draft \n \n David Kirk/NVIDIA and Wen-mei Hwu, 2006-2016 \n9 \nin a block can access shared-memory variables allocated to the block. Shared memory is an \nefficient means for threads to cooperate by sharing their input data and intermediate results. \nBy declaring a CUDA variable in one of the CUDA memory types, a CUDA programmer \ndictates the visibility and access speed of the variable. \n \n \nFigure 4.6: Overview of the CUDA device memory model \n \nIn order to fully appreciate the difference between registers, shared memory and global \nmemory, we need to go into a little more details of how these different memory types are \nrealized and used in modern processors. Virtually all modern processors find their root in \nthe model proposed by John von Neumann in 1945, which is shown in Figure 4.7. The \nCUDA devices are no exception. The Global Memory in a CUDA device maps to the \nMemory box in Figure 4.7. The processor box corresponds to the processor chip boundary \nthat we typically see today. The Global Memory is off the processor chip and is implemented \nwith DRAM technology, which implies long access latencies and relatively low access \nbandwidth. The Registers correspond to the Register File of the von Neumann model. The \nRegister File is on the processor chip, which implies very short access latency and drastically \nhigher access bandwidth when compared to the global memory. In a typical device, the \naggregated access bandwidth of the register files is at least two orders of magnitude higher \nthan that of the global memory. Furthermore, whenever a variable is stored in a register, its \naccesses no longer consume off-chip global memory bandwidth. This will be reflected as an \nincreased compute-to-global-memory-access ratio.",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        12,
    "readable_filename":
        "3rd-Edition-Chapter07-convolution-FINAL-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter07-convolution-FINAL-corrected.pdf",
    "text":
        "Third Edition \n \nPreproduction Draft \n David Kirk/NVIDIA and Wen-mei Hwu, 2006-2016 \n12 \nelements into an on-chip memory and then access the on-chip memory for their subsequent \nuse of these elements. For simplicity, we will continue to assume that each thread calculates \none output P element. With up to 1024 threads in a block we can process up to 1024 data \nelements. We will refer to the collection of output elements processed by each block as an \noutput tile. Figure 7.10 shows a small example of 16-element 1D convolution using four \nthread blocks of four threads each. In this example, there are four output tiles. The first output \ntile covers N[0] through N[3], the second tile N[4] through N[7], the third tile N[8] through \nN[11], and the fourth tile N[12] through N[15]. Keep in mind that we use four threads per \nblock to keep the example small. In practice, there should be at least 32 threads per block \nfor the current generation of hardware. From this point on, we will assume that M elements \nare in the constant memory. \n \nWe will discuss two input data tiling strategy for reducing the total number of global memory \naccesses. The first one is the most intuitive and involves loading all input data elements \nneeded for calculating all output elements of a thread block into the shared memory. The \nnumber of input elements to be loaded depends on the size of the mask. For simplicity, we \nwill continue to assume that the mask size is an odd number equal to 2*n+1. That is each \noutput element P[i] is a weighted sum of the input element at the corresponding input element \nN[i], the n input elements to the left (N[i-n],  N[i-1]), and the n input elements to the right \n(N[i+1],  N[i+n]). Figure 7.10 shows an example where Mask_Width=5 and n=2.  \n \n \nFigure 7.10 A 1D tiled convolution example. \n \nThreads in the Block 0 calculate output elements P[0] through P[3]. They collectively require \ninput elements N[0] through N[5]. Note that the calculation also requires two ghost cell \nelements to the left of N[0]. This is shown as two dashed empty elements on the left end of \nTile 0 of Figure 7.6. These ghost elements will be assumed have default value of 0. Tile 3 \nhas a similar situation at the right end of input array N.  In our discussions, we will refer to",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        36,
    "readable_filename":
        "ece408-lecture5-CUDA-tiled-matrix-multiplication-vk-FA23.pdf",
    "s3_path":
        "courses/ECE408FA23/ece408-lecture5-CUDA-tiled-matrix-multiplication-vk-FA23.pdf",
    "text":
        "36\nAnother Good Choice: 32x32 Tiles\n Given TILE_WIDTH of 32 (1,024 threads / block),\n each thread block uses \n2*1024*4B = 8kB of shared memory,\n which limits active blocks to 8;\n max. of 2,048 threads per SM,\n which limits blocks to 2.\n Thus up to 2*2,048 = 4,096 pending loads \n(2 per thread, 1,024 threads per block)\n(same memory parallelism exposed) \n David Kirk/NVIDIA and Wen-mei W. Hwu, 2007-2018 \nECE408/CS483/ University of Illinois at Urbana-Champaign",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        3,
    "readable_filename":
        "3rd-Edition-Chapter05-performance-FINAL-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter05-performance-FINAL-corrected.pdf",
    "text":
        "Third Edition \n \nPreproduction Draft \n \n David Kirk and Wen-mei Hwu, 2006-2016 \n3 \n \n \n \nThe global memory of a CUDA device is implemented with DRAMs. Data bits are stored \nin DRAM cells that are small capacitors, where the presence or absence of a tiny amount \nof electrical charge distinguishes between 0 and 1. Reading data from a DRAM cell \nrequires the small capacitor to use its tiny electrical charge to drive a highly capacitive line \nleading to a sensor and set off its detection mechanism that determines whether a sufficient \namount of charge is present in the capacitor to qualify as a 1  (see Why is DRAM so \nslow? sidebar). This process takes 10s of nanoseconds in modern DRAM chips. This is \nin sharp contrast with the sub-nanosecond clock cycle time of modern computing devices. \nBecause this is a very slow process relative to the desired data access speed (sub-\nnanosecond access per byte), modern DRAMs use parallelism to increase their rate of data \naccess, commonly referred to as memory access throughput.  \n \nEach time a DRAM location is accessed, a range of consecutive locations that include the \nrequested location are actually accessed. Many sensors are provided in each DRAM chip \nand they work in parallel. Each senses the content of a bit within these consecutive \nlocations. Once detected by the sensors, the data from all these consecutive locations can \nbe transferred at very high speed to the processor. These consecutive locations accessed \nand delivered are referred to as DRAM bursts. If an application makes focused use of data \nfrom these bursts, the DRAMs can supply the data at much higher rate than if a truly \nrandom sequence of locations were accessed.  \n \nRecognizing the burst organization of modern DRAMs, current CUDA devices employ a \ntechnique that allows the programmers to achieve high global memory access efficiency \nby organizing memory accesses of threads into favorable patterns. This technique takes \nadvantage of the fact that threads in a warp execute the same instruction at any given point \nin time. When all threads in a warp execute a load instruction, the hardware detects whether \nthey access consecutive global memory locations.  That is, the most favorable access \npattern is achieved when all threads in a warp access consecutive global memory locations. \nIn this case, the hardware combines, or coalesces, all these accesses into a consolidated \naccess to consecutive DRAM locations. For example, for a given load instruction of a warp, \nif thread 0 accesses global memory location N2, thread 1 location N+1, thread 2 location \nN+2, and so on, all these accesses will be coalesced, or combined into a single request for \nconsecutive locations when accessing the DRAMs. Such coalesced access allows the \nDRAMs to deliver data as a burst.3 \n                                                 \n2 Different CUDA devices may also impose alignment requirements on N. For example, in some CUDA \ndevices, N  is required to be aligned to 16-word boundaries. That is, the lower 6 bits of N should all be 0 \nbits. Such alignment requirements have been relaxed in recent CUDA devices due to the presence of \nsecond-level caches. \n3 Note that modern CPUs also recognize the DRAM burst organization in their cache memory design. A \nCPU cache line typically maps to one or more DRAM bursts. Applications that make full use of bytes in",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        155,
    "readable_filename":
        "CUDA_C_Programming_Guide.pdf",
    "s3_path":
        "courses/ECE408FA23/CUDA_C_Programming_Guide.pdf",
    "text":
        "CUDA C++ Programming Guide, Release 12.2\n Write the results back to device memory.\nFor some applications (for example, for which global memory access patterns are data-dependent),\na traditional hardware-managed cache is more appropriate to exploit data locality. As mentioned in\nCompute Capability 7.x, Compute Capability 8.x and Compute Capability 9.0, for devices of compute\ncapability 7.x, 8.x and 9.0, the same on-chip memory is used for both L1 and shared memory, and how\nmuch of it is dedicated to L1 versus shared memory is configurable for each kernel call.\nThe throughput of memory accesses by a kernel can vary by an order of magnitude depending on ac-\ncess pattern for each type of memory. The next step in maximizing memory throughput is therefore\nto organize memory accesses as optimally as possible based on the optimal memory access patterns\ndescribed in Device Memory Accesses. This optimization is especially important for global memory\naccesses as global memory bandwidth is low compared to available on-chip bandwidths and arith-\nmetic instruction throughput, so non-optimal global memory accesses generally have a high impact\non performance.\n8.3.1. Data Transfer between Host and Device\nApplications should strive to minimize data transfer between the host and the device. One way to\naccomplish this is to move more code from the host to the device, even if that means running kernels\nthat do not expose enough parallelism to execute on the device with full efficiency. Intermediate data\nstructures may be created in device memory, operated on by the device, and destroyed without ever\nbeing mapped by the host or copied to host memory.\nAlso, because of the overhead associated with each transfer, batching many small transfers into a\nsingle large transfer always performs better than making each transfer separately.\nOn systems with a front-side bus, higher performance for data transfers between host and device is\nachieved by using page-locked host memory as described in Page-Locked Host Memory.\nIn addition, when using mapped page-locked memory (Mapped Memory), there is no need to allocate\nany device memory and explicitly copy data between device and host memory. Data transfers are\nimplicitly performed each time the kernel accesses the mapped memory. For maximum performance,\nthese memory accesses must be coalesced as with accesses to global memory (see Device Memory\nAccesses). Assuming that they are and that the mapped memory is read or written only once, using\nmapped page-locked memory instead of explicit copies between device and host memory can be a\nwin for performance.\nOn integrated systems where device memory and host memory are physically the same, any copy\nbetween host and device memory is superfluous and mapped page-locked memory should be used\ninstead. Applications may query a device is integrated by checking that the integrated device prop-\nerty (see Device Enumeration) is equal to 1.\n8.3.2. Device Memory Accesses\nAn instruction that accesses addressable memory (i.e., global, local, shared, constant, or texture mem-\nory) might need to be re-issued multiple times depending on the distribution of the memory addresses\nacross the threads within the warp. How the distribution affects the instruction throughput this way\nis specific to each type of memory and described in the following sections. For example, for global\nmemory, as a general rule, the more scattered the addresses are, the more reduced the throughput is.\nGlobal Memory\n8.3. Maximize Memory Throughput\n139",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        1,
    "readable_filename":
        "3rd-Edition-Chapter05-performance-FINAL-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter05-performance-FINAL-corrected.pdf",
    "text":
        "Third Edition \n \nPreproduction Draft \n \n David Kirk and Wen-mei Hwu, 2006-2016 \n1 \n \n \nChapter 5 \nPerformance Considerations \n \n \nKeywords: compute-bound, memory-bound, bottleneck, memory bandwidth, DRAM \nburst, memory coalescing, corner turning, memory bank, memory channel, SIMD, control \nflow, control divergence, dynamic resource partition, instruction mix, thread granularity \n \n \nCHAPTER OUTLINE \n5.1. Global Memory Bandwidth \n5.2. More on Memory Parallelism \n5.3. Warps and SIMD Hardware \n5.4. Dynamic Partitioning of Resources \n5.5. Thread Granularity \n5.6. Summary \n5.7. Exercises \n \n \nThe execution speed of a parallel program can vary greatly depending on the resource \nconstraints of the computing hardware. While managing the interaction between parallel \ncode and hardware resource constraints is important for achieving high performance in \nvirtually all parallel programming models, it is a practical skill that is best learnt with \nhands-on exercises in a parallel programming model designed for high-performance. In \nthis chapter, we will discuss the major types of resource constraints in a CUDA device and \nhow they can affect the kernel execution performance. In order to achieve his/her goals, a \nprogrammer often has to find ways to achieve a required level of performance that is higher \nthan that of an initial version of the application. In different applications, different \nconstraints may dominate and become the limiting factors, commonly referred to as \nbottlenecks. One can often dramatically improve the performance of an application on a \nparticular CUDA device, by trading one resource usage for another. This strategy works \nwell if the resource constraint thus alleviated was actually the dominating constraint before \nthe strategy was applied and the one thus exacerbated does not have negative effects on \nparallel execution. Without such understanding, performance tuning would be a guess",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        34,
    "readable_filename":
        "ece408-lecture1-introduction-vk-FA23.pdf",
    "s3_path":
        "courses/ECE408FA23/ece408-lecture1-introduction-vk-FA23.pdf",
    "text":
        "Global Memory Bandwidth\nIdeal\nReality\n37\n David Kirk/NVIDIA and Wen-mei W. Hwu, 2007-2018 \nECE408/CS483/ University of Illinois at Urbana-Champaign",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        157,
    "readable_filename":
        "CUDA_C_Programming_Guide.pdf",
    "s3_path":
        "courses/ECE408FA23/CUDA_C_Programming_Guide.pdf",
    "text":
        "CUDA C++ Programming Guide, Release 12.2\nReading non-naturally aligned 8-byte or 16-byte words produces incorrect results (off by a few words),\nso special care must be taken to maintain alignment of the starting address of any value or array of\nvalues of these types. A typical case where this might be easily overlooked is when using some cus-\ntom global memory allocation scheme, whereby the allocations of multiple arrays (with multiple calls\nto cudaMalloc() or cuMemAlloc()) is replaced by the allocation of a single large block of memory\npartitioned into multiple arrays, in which case the starting address of each array is offset from the\nblocks starting address.\nTwo-Dimensional Arrays\nA common global memory access pattern is when each thread of index (tx,ty) uses the following\naddress to access one element of a 2D array of width width, located at address BaseAddress of type\ntype* (where type meets the requirement described in Maximize Utilization):\nBaseAddress + width * ty + tx\nFor these accesses to be fully coalesced, both the width of the thread block and the width of the array\nmust be a multiple of the warp size.\nIn particular, this means that an array whose width is not a multiple of this size will be accessed much\nmore efficiently if it is actually allocated with a width rounded up to the closest multiple of this size\nand its rows padded accordingly. The cudaMallocPitch() and cuMemAllocPitch() functions and\nassociated memory copy functions described in the reference manual enable programmers to write\nnon-hardware-dependent code to allocate arrays that conform to these constraints.\nLocal Memory\nLocal memory accesses only occur for some automatic variables as mentioned in Variable Memory\nSpace Specifiers. Automatic variables that the compiler is likely to place in local memory are:\n Arrays for which it cannot determine that they are indexed with constant quantities,\n Large structures or arrays that would consume too much register space,\n Any variable if the kernel uses more registers than available (this is also known as register spilling).\nInspection of the PTX assembly code (obtained by compiling with the -ptx or-keep option) will tell if a\nvariable has been placed in local memory during the first compilation phases as it will be declared using\nthe .local mnemonic and accessed using the ld.local and st.local mnemonics. Even if it has not,\nsubsequent compilation phases might still decide otherwise though if they find it consumes too much\nregister space for the targeted architecture: Inspection of the cubin object using cuobjdump will tell if\nthis is the case. Also, the compiler reports total local memory usage per kernel (lmem) when compiling\nwith the --ptxas-options=-v option. Note that some mathematical functions have implementation\npaths that might access local memory.\nThe local memory space resides in device memory, so local memory accesses have the same high\nlatency and low bandwidth as global memory accesses and are subject to the same requirements for\nmemory coalescing as described in Device Memory Accesses. Local memory is however organized\nsuch that consecutive 32-bit words are accessed by consecutive thread IDs. Accesses are therefore\nfully coalesced as long as all threads in a warp access the same relative address (for example, same\nindex in an array variable, same member in a structure variable).\nOn devices of compute capability 5.x onwards, local memory accesses are always cached in L2 in the\nsame way as global memory accesses (see Compute Capability 5.x and Compute Capability 6.x).\nShared Memory\nBecause it is on-chip, shared memory has much higher bandwidth and much lower latency than local\nor global memory.\n8.3. Maximize Memory Throughput\n141",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        17,
    "readable_filename":
        "3rd-Edition-Chapter07-convolution-FINAL-corrected.pdf",
    "s3_path":
        "courses/ECE408FA23/3rd-Edition-Chapter07-convolution-FINAL-corrected.pdf",
    "text":
        "Third Edition \n \nPreproduction Draft \n David Kirk/NVIDIA and Wen-mei Hwu, 2006-2016 \n17 \n \nFor most situations, blockDim.x is much larger than n. Both ratios can be approximated by \neliminating the small terms n(n+1)/2 and n: \n \n(blockDim.x*(2n+1)/ blockDim.x = 2n+1 = Mask_Width \n \nThis should be quite an intuitive result. In the original algorithm, each N element is \nredundantly loaded by approximately Mask_Width threads. For example, in Figure 7.12, \nN[2] is loaded by the 5 threads that calculate P[2], P[3], P[4], P[5], and P[6]. That is, the ratio \nof memory access reduction is approximately proportional to the mask size. \n \nHowever, in practice, the effect of the smaller terms may be significant and cannot be \nignored. For example, if blockDim.x is 128 and n is 5, the ratio for the internal blocks is \n \n(128*11  10) / (128 + 10) = 1398 / 138 = 10.13 \n \nwhereas the approximate ratio would be 11. It should be clear that as the blockDim.x  \nbecomes smaller, the ratio also becomes smaller. For example, if blockDim is 32 and n is 5, \nthe ratio for the internal blocks becomes \n \n(32*11  10) / (32+10) = 8.14 \n \nThe readers should always be careful when using smaller block and tile sizes. They may \nresult in significantly less reduction in memory accesses than expected. In practice, smaller \ntile sizes are often used due to insufficient amount of on-chip memory, especially for 2D and \n3D convolution where the amount of on-chip memory needed grow quickly with the \ndimension of the tile. \n7.5. A Simpler Tiled 1D Convolution - General Caching \nIn Figure 7.11, much of the complexity of the code has to do with loading the left and right \nhalo cells in addition to the internal elements into the shared memory. More recent GPUs \nsuch as Fermi provide general L1 and L2 caches, where L1 is private to each streaming \nmultiprocessor and L2 is shared among all streaming multiprocessors.  This leads to an \nopportunity for the blocks to take advantage of the fact that their halo cells may be available \nin the L2 cache. \n \nRecall that the halo cells of a block are also internal cells of a neighboring block. For \nexample, in Figure 7.10, the halo cells N[2] and N[3] of Tile 1 are also internal elements of \nTile 0. There is a significant probability that by the time Block 1 needs to use these halo \ncells, they are already in L2 cache due to the accesses by Block 0. As a result, the memory \naccesses to these halo cells may be naturally served from L2 cache without causing \nadditional DRAM traffic. That is, we can leave the accesses to these halo cells in the original \nN elements rather than loading them into the N_ds. We now present a simpler tiled 1D",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        156,
    "readable_filename":
        "CUDA_C_Programming_Guide.pdf",
    "s3_path":
        "courses/ECE408FA23/CUDA_C_Programming_Guide.pdf",
    "text":
        "CUDA C++ Programming Guide, Release 12.2\nGlobal memory resides in device memory and device memory is accessed via 32-, 64-, or 128-byte\nmemory transactions. These memory transactions must be naturally aligned: Only the 32-, 64-, or 128-\nbyte segments of device memory that are aligned to their size (i.e., whose first address is a multiple\nof their size) can be read or written by memory transactions.\nWhen a warp executes an instruction that accesses global memory, it coalesces the memory accesses\nof the threads within the warp into one or more of these memory transactions depending on the size\nof the word accessed by each thread and the distribution of the memory addresses across the threads.\nIn general, the more transactions are necessary, the more unused words are transferred in addition to\nthe words accessed by the threads, reducing the instruction throughput accordingly. For example, if a\n32-byte memory transaction is generated for each threads 4-byte access, throughput is divided by 8.\nHow many transactions are necessary and how much throughput is ultimately affected varies with the\ncompute capability of the device. Compute Capability 5.x, Compute Capability 6.x, Compute Capabil-\nity 7.x, Compute Capability 8.x and Compute Capability 9.0 give more details on how global memory\naccesses are handled for various compute capabilities.\nTo maximize global memory throughput, it is therefore important to maximize coalescing by:\n Following the most optimal access patterns based on Compute Capability 5.x, Compute Capabil-\nity 6.x, Compute Capability 7.x, Compute Capability 8.x and Compute Capability 9.0\n Using data types that meet the size and alignment requirement detailed in the section Size and\nAlignment Requirement below,\n Padding data in some cases, for example, when accessing a two-dimensional array as described\nin the section Two-Dimensional Arrays below.\nSize and Alignment Requirement\nGlobal memory instructions support reading or writing words of size equal to 1, 2, 4, 8, or 16 bytes.\nAny access (via a variable or a pointer) to data residing in global memory compiles to a single global\nmemory instruction if and only if the size of the data type is 1, 2, 4, 8, or 16 bytes and the data is\nnaturally aligned (i.e., its address is a multiple of that size).\nIf this size and alignment requirement is not fulfilled, the access compiles to multiple instructions\nwith interleaved access patterns that prevent these instructions from fully coalescing. It is therefore\nrecommended to use types that meet this requirement for data that resides in global memory.\nThe alignment requirement is automatically fulfilled for the Built-in Vector Types.\nFor structures, the size and alignment requirements can be enforced by the compiler using the align-\nment specifiers__align__(8) or __align__(16), such as\nstruct __align__(8) {\nfloat x;\nfloat y;\n};\nor\nstruct __align__(16) {\nfloat x;\nfloat y;\nfloat z;\n};\nAny address of a variable residing in global memory or returned by one of the memory allocation rou-\ntines from the driver or runtime API is always aligned to at least 256 bytes.\n140\nChapter 8. Performance Guidelines",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        9,
    "readable_filename":
        "ece408-lecture8-tiled-convolution-vk-FA23.pdf",
    "s3_path":
        "courses/ECE408FA23/ece408-lecture8-tiled-convolution-vk-FA23.pdf",
    "text":
        "Should We Use Shared Memory?\nIn other words,\nCan we reuse data read from global memory?\nLets look at the computation again\nReuse reduces global memory bandwidth,\nso lets use shared memory.\n Steven S. Lumetta\nECE408/CS483/ECE498al University of Illinois, 2020\n9\noutputs\ninputs",
    "url":
        ""
}, {
    "base_url":
        "",
    "course_name ":
        "ECE408FA23",
    "pagenumber":
        26,
    "readable_filename":
        "ece408-lecture8-tiled-convolution-vk-FA23.pdf",
    "s3_path":
        "courses/ECE408FA23/ece408-lecture8-tiled-convolution-vk-FA23.pdf",
    "text":
        "Strategy 2: Parallelize Loading of a Tile\nAlternately,\n each thread loads one input element, and\n some threads compute an output.\n(compared with previous approach)\nAdvantage:\n No branch divergence for load (high latency).\n Avoid narrow global access (2  halo width).\nDisadvantage:\n Branch divergence for compute (low latency).\n Steven S. Lumetta\nECE408/CS483/ECE498al University of Illinois, 2020\n26",
    "url":
        ""
}]


@ray.remote
class AsyncActor:

  def __init__(self):
    pass

  def filter_context(self, context, user_query, langsmith_prompt_obj):
    final_prompt = str(langsmith_prompt_obj.format(context=context, user_query=user_query))
    # print(f"-------\nfinal_prompt:\n{final_prompt}\n^^^^^^^^^^^^^")
    try:
      # completion = run_model(final_prompt)
      # completion = run_replicate(final_prompt)
      completion = run_anyscale(final_prompt)
      return {"completion": completion, "context": context}
    except Exception as e:
      print(f"Error: {e}")


def run_model(prompt, max_tokens=300, temp=0.3, **kwargs):
  """
  Local LLMs  USAGE DOCS: https://kastanday.notion.site/LLM-Serving-on-prem-OpenAI-Clone-bb06028266d842b0872465f552684177 ## 
  """

  url = "http://api.kastan.ai/v1/completions?model=HuggingFaceH4/zephyr-7b-alpha"
  headers = {'Content-Type': 'application/json'}
  data = {"prompt": prompt, "max_tokens": max_tokens, "temperature": temp, **kwargs}

  try:
    response = requests.post(url, headers=headers, data=json.dumps(data))
    return response.json()['choices'][0]['text']
  except Exception as e:
    # Probably cuda OOM error.
    raise ValueError(
        f"🚫🚫🚫 Failed inference attempt. Response: {response.json()}\nError: {e}\nPromt that caused error: {prompt}")


def run_replicate(prompt):
  output = replicate.run("tomasmcm/zephyr-7b-beta:961cd6665b811d0c43c0b9488b6dfa85ff5c7bfb875e93b4533e4c7f96c7c526",
                         input={
                             "top_k": 50,
                             "top_p": 0.95,
                             "prompt": prompt,
                             "temperature": 0.3,
                             "max_new_tokens": 250,
                             "presence_penalty": 1
                         })
  print(output)
  return output


def run_anyscale(prompt, model_name="HuggingFaceH4/zephyr-7b-beta"):
  start_time = time.monotonic()
  ret = openai.ChatCompletion.create(
      api_base="https://api.endpoints.anyscale.com/v1",
      api_key=os.environ["ANYSCALE_ENDPOINT_TOKEN"],
      model="mistralai/Mistral-7B-Instruct-v0.1",
      api_type="openai",
      # model="HuggingFaceH4/zephyr-7b-beta",
      messages=[{
          "role": "system",
          "content": "You are a helpful assistant."
      }, {
          "role": "user",
          "content": prompt
      }],
      temperature=0.3,
      max_tokens=250,
  )

  output = ret["choices"][0]["message"]["content"]
  print("Output:", output[:40])

  input_length = len(tokenizer.encode(prompt))
  output_length = len(tokenizer.encode(output))

  print(
      f"🧠 ^^^^ one anyscale call Runtime: {(time.monotonic() - start_time):.2f} seconds. Input tokens {input_length}, output tokens: {output_length}"
  )

  return output


def parse_result(result):
  lines = result.split('\n')
  for line in lines:
    if 'Final answer' in line:
      return 'yes' in line.lower()
  return False


def run(contexts, user_query, max_tokens_to_return=3000, max_time_before_return=None, max_concurrency=6):
  langsmith_prompt_obj = hub.pull("kastanday/filter-unrelated-contexts-zephyr")

  print("Max concurrency:", max_concurrency)

  print("Num jobs to run:", len(contexts))

  actor = AsyncActor.options(max_concurrency=max_concurrency).remote()
  result_futures = [actor.filter_context.remote(c, user_query, langsmith_prompt_obj) for c in contexts]

  start_time = time.time()
  for i in range(0, len(result_futures)):
    try:
      ready, not_ready = ray.wait(result_futures)
      result = ray.get(ready[0])

      if result is None:
        print("RESULT WAS NONE, llm inference probably failed")
        continue

      if parse_result(result['completion']):
        yield result['context']

      elapsed_time = (time.time() - start_time)
      avg_task_time = elapsed_time / (i + 1)
      estimated_total_runtime = avg_task_time * len(contexts)

      print(f"📌 Completed {i+1} of {len(contexts)}")
      print(
          f"⏰ Running total of elapsed time: {elapsed_time:.2f} seconds\n🔮 Estimated total runtime: {estimated_total_runtime:.2f} seconds.\n"
      )
      print(f"⏰👻 avg_task_time (s): {avg_task_time:.2f}")
      # print(f"📜 Passage: {result['context']['text']}")
      # print(f"✅ Result: {result['completion']}")

      if max_time_before_return is not None and elapsed_time >= max_time_before_return:
        break

    except Exception as e:
      print("-----------❌❌❌❌------------START OF ERROR-----------❌❌❌❌------------")
      print(f"Error in {inspect.currentframe().f_code.co_name}: {e}")  # print function name in error.
      print("Traceback:")
      print(traceback.print_exc())
    finally:
      result_futures = not_ready
      if not result_futures:
        break


def run_main():
  ray.init()
  start_time = time.monotonic()
  # print(len(CONTEXTS))
  final_passage_list = list(
      run(contexts=CONTEXTS * 2, user_query=USER_QUERY, max_time_before_return=45, max_concurrency=200))

  print("✅✅✅ FINAL RESULTS: \n" + '\n'.join(json.dumps(r, indent=2) for r in final_passage_list))
  print("✅✅✅ TOTAL RETURNED: ", len(final_passage_list))
  print(f"⏰⏰⏰ Runtime: {(time.monotonic() - start_time):.2f} seconds")
  print("Total contexts:", len(CONTEXTS) * 2)


# ! CONDA ENV: llm-serving
if __name__ == "__main__":
  run_main()
