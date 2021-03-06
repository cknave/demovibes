/*
*   demosauce - fancy icecast source client
*
*   this source is published under the GPLv3 license.
*   http://www.gnu.org/licenses/gpl.txt
*   also, this is beerware! you are strongly encouraged to invite the
*   authors of this software to a beer when you happen to meet them.
*   copyright MMXI by maep
*/

#ifndef _H_BASSSOURCE_
#define _H_BASSSOURCE_

#include <string>

#include <boost/cstdint.hpp>
#include <boost/scoped_ptr.hpp>

#include "audiostream.h"

class BassSource : public Decoder
{
public:
    BassSource();
    virtual ~BassSource();
    static bool probe_name(std::string file_name);

    // manipulators
    // only applies to modules
    void set_samplerate(uint32_t samplerate);
    // only applies to modules
    void set_loop_duration(double duration);
    bool load(std::string fileName, bool prescan);
    bool load(std::string file_name, std::string playback_settings);

    // manipulators from AbstractSource
    bool load(std::string file_name);
    void process(AudioStream& stream, uint32_t frames);
    void seek(uint64_t frame);

    // observers
    bool is_module() const;
    bool is_amiga_module() const;
    float loopiness() const;

    // observers from AbstractSource
    std::string name() const;
    uint32_t channels() const;
    uint32_t samplerate() const;
    uint64_t length() const;
    float bitrate() const;
    bool seekable() const;
    std::string metadata(std::string key) const;

private:
    struct Pimpl;
    boost::scoped_ptr<Pimpl> pimpl;
};

#endif
