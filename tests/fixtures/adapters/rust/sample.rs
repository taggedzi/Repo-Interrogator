pub mod engine {
    pub const VERSION: &str = "1.0";
}

pub struct Service {
    name: String,
}

pub enum Mode {
    Fast,
    Slow,
}

pub trait Runner {
    fn run(&self, input: &str) -> String;
}

pub const DEFAULT_NAME: &str = "service";
pub type ResultText = String;

pub fn build(name: String) -> Service {
    Service { name }
}

impl Service {
    pub fn new(name: String) -> Self {
        Self { name }
    }

    pub async fn run(&self, input: &str) -> String {
        format!("{}:{}", self.name, input)
    }
}

impl Runner for Service {
    fn run(&self, input: &str) -> String {
        input.to_owned()
    }
}
