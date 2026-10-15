//! Runs GNOME Camera's document scanner (src/document.rs of the patched
//! gnome-snapshot tree) on photos: doctest a.jpg b.jpg ...
//!
//!   DOC_DEBUG=1        log the page candidates
//!   DOC_TURNS=1        quarter turns clockwise
//!   DOC_FILTER=off|clean|black-white   filter (default clean)
//!   DOC_PDF=out.pdf    also write all scans into one PDF
//!   DOC_NOSAVE=1       only find the page (corners and timing)
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
    let options = document::ScanOptions {
        quarter_turns: std::env::var("DOC_TURNS").ok().and_then(|v| v.parse().ok()).unwrap_or(0),
        filter: document::ScanFilter::from_str(&std::env::var("DOC_FILTER").unwrap_or_default()),
    };
    let mut scans = Vec::new();
    for f in std::env::args().skip(1) {
        // NAME_WxH.rgb: a raw preview-sized frame, timed through the live
        // outline's detection
        if let Some(dims) = f.strip_suffix(".rgb").and_then(|s| s.rsplit('_').next()) {
            let (w, h) = dims.split_once('x').unwrap();
            let (w, h): (usize, usize) = (w.parse().unwrap(), h.parse().unwrap());
            let rgb = std::fs::read(&f).unwrap();
            let t = std::time::Instant::now();
            let mut c = None;
            for _ in 0..10 {
                c = document::find_page_in_frame(w, h, w * 3, &rgb);
            }
            println!(
                "{f}: corners {:?} in {:.1} ms",
                c.map(|c| c.map(|(x, y)| (x as i32, y as i32))),
                t.elapsed().as_secs_f64() * 100.0
            );
            continue;
        }
        let p = std::path::Path::new(&f);
        let prep = match document::prepare(p) {
            Ok(prep) => prep,
            Err(e) => {
                println!("{f}: {e:#}");
                continue;
            }
        };
        let c = prep.corners;
        println!(
            "{f}: corners {:?}{}",
            c.map(|(x, y)| (x as i32, y as i32)),
            if prep.detected { "" } else { " (not found, default)" }
        );
        if std::env::var_os("DOC_NOSAVE").is_some() {
            continue;
        }
        let out = document::scan_path(p);
        match document::save_scan(&prep, &prep.corners, options, &out) {
            Ok(()) => {
                println!("{f}: -> {}", out.display());
                scans.push(out);
            }
            Err(e) => println!("{f}: {e:#}"),
        }
    }
    if let Some(pdf) = std::env::var_os("DOC_PDF") {
        match document::write_pdf(&scans, std::path::Path::new(&pdf)) {
            Ok(()) => println!("pdf: {} pages -> {}", scans.len(), pdf.to_string_lossy()),
            Err(e) => println!("pdf: {e:#}"),
        }
    }
}
