# What is Tuna
As a high-performance kernels library, MIOpen needs a substantive tuning effort to discover the
optimal tuning parameters. Kernel tuning entails compiling and running MIOpen kernels with different
tuning parameters to determine the best performing tuning parameters for each kernel. While MIOpen
contains much of the logic needed to iterate over possible tuning parameters, it is only applicable
to a single machine. Therefore, a mechanism is required to parallelize this process across different
machines as well as across multiple GPUs to speed up this inherently parallel procedure. Among other
features, such a framework, it needs to be able to handle errors in both MIOpen and the stack on which
MIOpen depends.

Tuna is MIOpens team library, which parallelizes the tuning procedure across multiple GPUs on
multiple machines. In addition to distributing jobs to servers, it is aware of the various
architectures, whether a tuning effort was successful, or resulted in an error and other housekeeping.
This makes it a useful automation tool. Tuna is also the custodian of the convolution layer parameters
of interest (to the MIOpen team), received from customers, as well as various benchmarks. With the
introduction of 'find database' for immediate mode, Tuna is also responsible for generating Find
database as well as the upcoming precompiled kernels package.

## When do we tune
There are two occasions that trigger tuning:
1. Someone opens a Github issue that contains the configurations and network to be tuned.
This implies we only need to tune the network specified in the issue along with the
configurations specified. If the person requesting this did not mention any configurations,
please ask for them. The Tuna team does not provide these.
2. Recurrent configurations need retuning when internals of MIOpen/Tuna change. The tuning
phase of all the recurrent configurations takes up to a few days. There are many configurations
used for each network and one should try and use as many machines as possible to speed up
the tuning part. The current configurations we tune for are:
