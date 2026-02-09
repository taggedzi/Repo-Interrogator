namespace Acme.Tools;

public interface IRunner
{
    string Run(string input);
}

public enum Mode
{
    Fast,
    Slow,
}

public record Result(bool Ok);

public class Service
{
    public string Name { get; init; }

    public event EventHandler? Changed;

    public Service(string name)
    {
        Name = name;
    }

    public async Task<string> RunAsync(string input)
    {
        return $"{Name}:{input}";
    }

    public static Service Build(string name)
    {
        return new Service(name);
    }
}
