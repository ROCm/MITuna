/*******************************************************************************
 *
 * MIT License
 *
 * Copyright (c) 2022 Advanced Micro Devices, Inc.
 *
 * Permission is hereby granted, free of charge, to any person obtaining a copy
 * of this software and associated documentation files (the "Software"), to deal
 * in the Software without restriction, including without limitation the rights
 * to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
 * copies of the Software, and to permit persons to whom the Software is
 * furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all
 * copies or substantial portions of the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
 * IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
 * FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
 * LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
 * OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
 * SOFTWARE.
 *
 *******************************************************************************/
#include <boost/algorithm/string.hpp>
#include <boost/filesystem/path.hpp>
#include <boost/variant.hpp>

#include <algorithm>
#include <fstream>
#include <iostream>
#include <map>
#include <memory>
#include <sstream>
#include <string>
#include <tuple>
#include <vector>

using bpath = boost::filesystem::path;

enum class ResolveModes
{
    Off,
    Auto,
};

struct FilePos
{
    bpath file;
    unsigned int line;
};

static bool
SplitString(const std::string& str, std::string& key, std::string& value, const char separator)
{
    const auto key_size = str.find(separator);
    const auto is_key   = key_size != std::string::npos && key_size != 0;

    if(!is_key)
        return false;

    key   = str.substr(0, key_size);
    value = str.substr(key_size + 1);
    return true;
}

std::ostream& operator<<(std::ostream& stream, const FilePos& pos)
{
    stream << pos.file.c_str() << ':' << pos.line;
    return stream;
}

struct FileData
{
    FilePos source;
    std::string value;
};

struct Conflict
{
    std::map<std::string, std::vector<FileData>> items;

    void Add(const std::string& data, const FilePos& pos)
    {
        std::istringstream ss(data);
        std::string part;

        while(std::getline(ss, part, ';'))
            AddItem(part, pos);
    }

    private:
    void AddItem(const std::string& item, const FilePos& pos)
    {
        std::string id, value;
        if(!SplitString(item, id, value, ':'))
        {
            std::cerr << "W\tIll-formed record: id not found at " << pos << std::endl;
            return;
        }

        if(value.empty())
        {
            std::cerr << "W\tNone contents under the id: " << id << " at " << pos << std::endl;
            return;
        }

        auto found = items.find(id);

        if(found != items.end())
            found->second.push_back({pos, value});
        else
            items.emplace(id, std::vector<FileData>({{pos, value}}));
    }
};

class DbMerger
{
    public:
    void Execute(int nargs, char** cargs)
    {
        ParseArguments(nargs, cargs);

        for(auto& file : source_paths)
            ParseFile(file);

        Process();
    }

    private:
    ResolveModes resolve_mode = ResolveModes::Off;
    bpath destination_path;
    bpath conflicts_path;
    bpath conflict_commands_path;
    std::vector<bpath> source_paths;
    std::map<std::string, boost::variant<FileData, Conflict>> data;
    bpath commands_path;

    static void ExitWithError(const std::string& message, int exit_code = 1)
    {
        std::cerr << message << std::endl;
        std::exit(exit_code);
    }

    static void ExitWithHelp()
    {
        std::cout << "Usage:" << std::endl;
        std::cout << "pdbmerge [arguments] [--sources|-s] <paths to files to merge>" << std::endl;
        std::cout << "\tProcess files." << std::endl;
        std::cout << "pdbmerge --help|-h" << std::endl;
        std::cout << "\tPrint this help message." << std::endl;
        std::cout << std::endl;
        std::cout << "Arguments:" << std::endl;
        std::cout << "--output|-o <path>" << std::endl;
        std::cout << "\tPath to output file. Output will not be saved if no file provided."
                  << std::endl;
        std::cout << "--conflicts|-p <path>" << std::endl;
        std::cout << "\tPath to conflicts file. Conflicts will not be saved if no file provided."
                  << std::endl;
        std::cout << "--conflict_commands|-x <path>" << std::endl;
        std::cout << "\tPath to conflict commands file. Conflict commands will not be saved if no "
                     "file provided."
                  << std::endl;
        std::cout << "--commands|-c <path>" << std::endl;
        std::cout
            << "\tPath to file to dump all driver commands. Commands will not be dumped if no "
               "file provided. Automatically sets conflicts and conflict_commands if they are not "
               "set"
            << std::endl;
        std::cout << "--resolve|-r <0|1|auto|off>" << std::endl;
        std::cout << "\tMerge conflict resolve mode. Default: off." << std::endl;
        std::cout << "\t\tAuto/1: Values with more commas is used. If equal amount of commas "
                     "value met earlier is used."
                  << std::endl;
        std::cout << "\t\tOff/0: Values with any conflicts are ignored." << std::endl;
        std::exit(0);
    }

    void ParseArguments(int nargs, char** cargs)
    {
        auto sources = false;

        for(auto i = 1; i < nargs; i++)
        {
            const auto arg = std::string{cargs[i]};

            if(sources)
            {
                if(!std::ifstream{arg})
                    ExitWithError("F\tCan not open file " + arg, 2);
                source_paths.emplace_back(arg);
                continue;
            }

            if(arg == "-r" || arg == "--resolve")
            {
                if(++i >= nargs)
                    ExitWithError("F\tExpected a value after " + arg + " argument.", 2);
                const auto value = boost::algorithm::to_lower_copy(std::string{cargs[i]});

                if(value == "0" || value == "off")
                    resolve_mode = ResolveModes::Off;
                else if(value == "1" || value == "auto")
                    resolve_mode = ResolveModes::Auto;
                else
                    ExitWithError("F\tExpected 0, 1, off or auto value after " + arg + " argument.",
                                  2);
            }
            else if(arg == "-c" || arg == "--commands")
            {
                if(++i >= nargs)
                    ExitWithError("F\tExpected a path after " + arg + " argument.", 2);
                commands_path = cargs[i];
            }
            else if(arg == "-p" || arg == "--conflicts")
            {
                if(++i >= nargs)
                    ExitWithError("F\tExpected a path after " + arg + " argument.", 2);
                conflicts_path = cargs[i];
            }
            else if(arg == "-x" || arg == "--conflict_commands")
            {
                if(++i >= nargs)
                    ExitWithError("F\tExpected a path after " + arg + " argument.", 2);
                conflict_commands_path = cargs[i];
            }
            else if(arg == "-o" || arg == "--output")
            {
                if(++i >= nargs)
                    ExitWithError("F\tExpected a path after " + arg + " argument.", 2);
                destination_path = cargs[i];

                if(conflicts_path.empty())
                    conflicts_path = destination_path.string() + ".conflicts";
                if(conflict_commands_path.empty())
                    conflict_commands_path = destination_path.string() + ".options";
            }
            else if(arg == "-s" || arg == "--sources")
            {
                if(i >= nargs - 1)
                    ExitWithError("F\tExpected at least one path after " + arg + " argument.", 2);
                sources = true;
            }
            else if(arg == "-h" || arg == "--help")
            {
                ExitWithHelp();
            }
            else if(!arg.empty() && arg[0] != '-')
            {
                sources = true;
                --i;
            }
            else
            {
                ExitWithError("F\tUnknown argument:" + arg, 2);
            }
        }

        if(source_paths.empty())
            ExitWithError("F\tExpected at least one input file.", 2);
    }

    void ParseFile(const bpath& path)
    {
        std::ifstream file(path.string());
        std::string line;
        unsigned int line_number = 0;

        while(std::getline(file, line))
        {
            line_number++;
            ParseLine({path, line_number}, line);
        }
    }

    void ParseLine(const FilePos& pos, const std::string& line)
    {
        if(line.empty())
            return;

        std::string key, value;

        if(!SplitString(line, key, value, '='))
        {
            std::cerr << "W\tIll-formed record: key not found at " << pos << std::endl;
            return;
        }

        if(value.empty())
        {
            std::cerr << "W\tNone contents under the key: " << key << " at " << pos << std::endl;
            return;
        }

        if(value[value.length() - 1] == '\r')
            value = value.substr(0, value.length() - 1);

        auto existing = data.find(key);

        if(existing != data.end())
        {
            if(const auto previous = boost::get<FileData>(&existing->second))
            {
                Conflict conflict;
                conflict.Add(previous->value, previous->source);
                conflict.Add(value, pos);
                existing->second = conflict;
            }
            else
            {
                auto& conflict = boost::get<Conflict>(existing->second);
                conflict.Add(value, pos);
            }
            return;
        }

        data.emplace(key, FileData{pos, value});
    }

    static bool AllEqual(const std::vector<FileData>& items)
    {
        for(auto i = 1u; i < items.size(); ++i)
            if(items[i].value != items[i - 1].value)
                return false;

        return true;
    }

    static std::tuple<int, int> SplitByX(const std::string& part)
    {
        const auto splitter = part.find('x');
        const auto p0       = std::stoi(part.substr(0, splitter));
        const auto p1       = std::stoi(part.substr(splitter + 1));
        return std::make_tuple(p0, p1);
    }

    static std::string OptionsFromKey(const std::string& key)
    {
        std::ostringstream options;
        std::istringstream in(key);
        std::string part;
        std::string main_arg;
        auto part_id = 0u;

        while(std::getline(in, part, '-'))
        {
            switch(part_id)
            {
            case 0: options << " -c " << std::stoi(part); break;
            case 1: options << " -H " << std::stoi(part); break;
            case 2: options << " -W " << std::stoi(part); break;
            case 3:
                int kernel_size1;
                int kernel_size0;
                std::tie(kernel_size1, kernel_size0) = SplitByX(part);
                options << " -x " << kernel_size0;
                options << " -y " << kernel_size1;
                break;
            case 4: options << " -k " << std::stoi(part); break;
            case 5: /*out_height*/ break;
            case 6: /*out_width*/ break;
            case 7: options << " -n " << std::stoi(part); break;
            case 8:
                int pad1;
                int pad0;
                std::tie(pad1, pad0) = SplitByX(part);
                options << " -p " << pad1;
                options << " -q " << pad0;
                break;
            case 9:
                int kernel_stride1;
                int kernel_stride0;
                std::tie(kernel_stride1, kernel_stride0) = SplitByX(part);
                options << " -u " << kernel_stride0;
                options << " -v " << kernel_stride1;
                break;
            case 10:
                int kernel_dilation1;
                int kernel_dilation0;
                std::tie(kernel_dilation1, kernel_dilation0) = SplitByX(part);
                options << " -l " << kernel_dilation0;
                options << " -j " << kernel_dilation1;
                break;
            case 11: options << " -b " << std::stoi(part); break;
            case 12: /*in_layout*/ break;
            case 13:
                if(part == "FP16")
                    main_arg = "fp16";
                else if(part == "FP32")
                    main_arg = "";
                else
                    ExitWithError("Unknown data type: " + part, 2);
                break;
            case 14: options << " -F " << (part == "F" ? 1 : 0); break;
            default: ExitWithError("Invalid db key: " + key, 2);
            }

            part_id++;
        }

        return main_arg + options.str();
    }

    void Process() const
    {
        auto exit_code = 0;

        if(resolve_mode == ResolveModes::Off)
        {
            if(!conflict_commands_path.empty() && !std::ofstream(conflict_commands_path.string()))
                ExitWithError("F\tCan not open file " + conflict_commands_path.string(), 2);
            if(!conflict_commands_path.empty() && !std::ofstream(conflicts_path.string()))
                ExitWithError("F\tCan not open file " + conflicts_path.string(), 2);
            if(!commands_path.empty() && !std::ofstream(commands_path.string()))
                ExitWithError("F\tCan not open file " + commands_path.string(), 2);
        }

        std::unique_ptr<std::ofstream> file{
            destination_path.empty() ? nullptr : new std::ofstream{destination_path.string()}};

        if(file && !*file)
            ExitWithError("F\tCan not open file " + destination_path.string(), 2);

        for(const auto& pair : data)
        {
            if(!commands_path.empty())
                std::ofstream(commands_path.string(), std::ios::app) << OptionsFromKey(pair.first)
                                                                     << std::endl;

            if(const auto value = boost::get<FileData>(&pair.second))
            {
                if(file)
                    *file << pair.first << '=' << value->value << std::endl;
            }
            else
            {
                const auto& conflict = boost::get<Conflict>(pair.second);
                if(!ProcessConflict(file.get(), pair.first, conflict))
                    exit_code = 1;
            }
        }

        std::exit(exit_code);
    }

    bool ProcessConflict(std::basic_ostream<char>* output,
                         const std::string& key,
                         const Conflict& conflict) const
    {
        if(resolve_mode == ResolveModes::Auto)
        {
            AutoResolve::Process(output, key, conflict);
            return true;
        }

        return NoResolve(conflict_commands_path, conflicts_path, output, key, conflict).Process();
    }

    struct AutoResolve
    {
        static std::string Resolve(const std::vector<FileData>& items)
        {
            auto best_metric = -1;
            auto best        = std::string{};

            for(const auto& item : items)
            {
                const auto metric = std::count(item.value.begin(), item.value.end(), ',');

                if(metric >= best_metric)
                {
                    best_metric = metric;
                    best        = item.value;
                }
            }

            return best;
        }

        static void
        Process(std::basic_ostream<char>* output, const std::string& key, const Conflict& conflict)
        {
            if(output == nullptr)
                return;

            *output << key << '=';
            for(const auto& id_pair : conflict.items)
                *output << id_pair.first << ':' << Resolve(id_pair.second);
            *output << std::endl;
        }
    };

    struct NoResolve
    {
        const bpath& options_path;
        const bpath& conflicts_path;
        std::basic_ostream<char>* output;
        const std::string key;
        const Conflict& conflict;

        NoResolve(const bpath& options_path_,
                  const bpath& conflicts_path_,
                  std::basic_ostream<char>* output_,
                  const std::string& key_,
                  const Conflict& conflict_)
            : options_path(options_path_),
              conflicts_path(conflicts_path_),
              output(output_),
              key(key_),
              conflict(conflict_)
        {
        }

        bool Process() const
        {
            auto no_conflicts = true;

            for(const auto& id_pair : conflict.items)
                if(!AllEqual(id_pair.second))
                {
                    no_conflicts = false;
                    break;
                }

            if(no_conflicts)
            {
                TrivialMerge();
                return true;
            }

            NoResolveMerge();
            return false;
        }

        void TrivialMerge() const
        {
            std::cerr << "W\tMerged without conflicts: " << key << std::endl;

            if(output == nullptr)
                return;

            *output << key << '=';

            auto first = true;
            for(const auto& id_pair : conflict.items)
            {
                if(!first)
                    *output << ';';

                first = false;
                *output << id_pair.first << ':' << id_pair.second[0].value;
            }

            *output << std::endl;
        }

        void NoResolveMerge() const
        {
            std::cerr << "E\tMerge conflict: " << key << std::endl;

            const auto driver_options = OptionsFromKey(key);
            WriteOptions(driver_options);
            WriteConflict(driver_options);
        }

        void WriteOptions(const std::string& driver_options) const
        {
            if(options_path.empty())
                return;

            std::ofstream options(options_path.string(), std::ios::app);
            options << driver_options << std::endl;
        }

        void WriteConflict(const std::string& driver_options) const
        {
            if(conflicts_path.empty())
                return;

            std::ofstream conflicts(conflicts_path.string(), std::ios::app);

            conflicts << "Merge conflict at key " << key << std::endl;
            conflicts << "Driver options to reproduce: " << driver_options << std::endl;
            conflicts << "Merged record: " << key << "=";

            auto first = true;
            for(const auto& id_pair : conflict.items)
                if(AllEqual(id_pair.second))
                {
                    if(!first)
                        conflicts << ';';

                    first = false;
                    conflicts << id_pair.first << ':' << id_pair.second[0].value;
                }

            conflicts << std::endl;
            conflicts << "Conflicting items:" << std::endl;

            for(const auto& id_pair : conflict.items)
                if(!AllEqual(id_pair.second))
                    for(const auto& source : id_pair.second)
                        conflicts << '\t' << id_pair.first << ':' << source.value << " from "
                                  << source.source << std::endl;

            conflicts << std::endl;
        }
    };
};

int main(int nargs, char** cargs)
{
    DbMerger{}.Execute(nargs, cargs);
    return 0;
}
