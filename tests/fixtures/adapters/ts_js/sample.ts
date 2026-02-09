export interface Runner {
  run(input: string): string;
}

export enum Mode {
  Fast,
  Slow,
}

export type Result = {
  ok: boolean;
};

export class Service {
  constructor(private readonly name: string) {}

  async run(input: string): Promise<string> {
    return `${this.name}:${input}`;
  }

  format(value: string): string {
    return value.trim();
  }
}

export async function build(name: string): Promise<Service> {
  return new Service(name);
}

export const DEFAULT_NAME = "service";
