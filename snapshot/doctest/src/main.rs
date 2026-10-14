//! Runs GNOME Camera's document scanner (src/document.rs of the patched
//! gnome-snapshot tree) on photos: doctest a.jpg b.jpg ...
#[path = "../../../vendor/snapshot-src/gnome-snapshot-50.0/src/document.rs"]
mod document;

struct DebugLog;
impl log::Log for DebugLog {
    fn enabled(&self, _: &log::Metadata) -> bool {
        true
    }
    fn log(&self, r: &log::Record) {
        eprintln!("  {}", r.args());
    }
    fn flush(&self) {}
}

fn main() {
    if std::env::var_os("DOC_DEBUG").is_some() {
        log::set_logger(&DebugLog).unwrap();
        log::set_max_level(log::LevelFilter::Debug);
    }
    for f in std::env::args().skip(1) {
        let p = std::path::Path::new(&f);
        if let Ok(c) = document::detect(p) {
            println!("{f}: corners {:?}", c.map(|(x, y)| (x as i32, y as i32)));
        }
        match document::scan(p) {
            Ok(out) => println!("{f}: -> {}", out.display()),
            Err(e) => println!("{f}: {e:#}"),
        }
    }
}
