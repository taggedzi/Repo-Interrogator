package com.example.service;

public interface Runner {
    String run(String input);
}

public enum Mode {
    FAST,
    SLOW
}

public record Result(boolean ok) {}

public class Service {
    private final String name;

    public Service(String name) {
        this.name = name;
    }

    public String run(String input) {
        return name + ":" + input;
    }

    private static int parse(int value) {
        return value + 1;
    }
}
