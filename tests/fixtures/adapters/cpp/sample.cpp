namespace engine {

class Service {
public:
    Service();
    int run(int value) const;
    static Service make();
};

struct Config {
    int retries;
    bool enabled() const;
};

enum Mode {
    Fast,
    Slow,
};

int parse_value(int input) {
    return input + 1;
}

} // namespace engine
