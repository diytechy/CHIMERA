plugins {
    `maven-publish`
}

group = "com.diytechy.terra.packs"
version = "2.0.1"

// Directories to exclude from the pack zip (beyond hidden dirs)
val excludedDirs = setOf(
    "OldPromptAndReviewReferences", "Review", ".artifacts", ".github",
    ".scripts", ".claude", ".idea", ".wiki", "memory", "images"
)

// Root-level files to keep (all others at root are excluded)
val allowedRootFiles = setOf("pack.yml", "meta.yml", "customization.yml", "substratum_meta.yml")

val packZip by tasks.registering(Zip::class) {
    archiveFileName.set("CHIMERA.zip")
    destinationDirectory.set(layout.buildDirectory.dir("artifacts"))

    from(projectDir) {
        // Include only the allowed root-level files
        include(allowedRootFiles.map { it })

        // Exclude all hidden files/dirs and the excluded dir list at root
        exclude { detail ->
            val name = detail.name
            val path = detail.path

            // Exclude hidden files/dirs (starting with . or _)
            if (name.startsWith(".") || name.startsWith("_")) return@exclude true

            // Exclude the named directories at any depth
            if (detail.isDirectory && excludedDirs.contains(name)) return@exclude true

            // Exclude root-level files that aren't in the allowed list
            if (!detail.isDirectory && !path.contains("/") && name !in allowedRootFiles) return@exclude true

            false
        }
    }

    // Include all subdirectories (excluding the ones listed above)
    from(projectDir) {
        include("biome-distribution/**", "biomes/**", "features/**", "structures/**",
                "math/**", "palettes/**", "functions/**", "samplers/**")
        exclude { detail ->
            val name = detail.name
            name.startsWith(".") || name.startsWith("_") ||
            (detail.isDirectory && excludedDirs.contains(name))
        }
    }
}

publishing {
    repositories {
        mavenLocal()
        maven {
            name = "Repsy"
            url = uri("https://repo.repsy.io/mvn/diytechy/terra-packs")
            credentials {
                username = project.findProperty("repsy.user") as String? ?: System.getenv("REPSY_USERNAME")
                password = project.findProperty("repsy.key") as String? ?: System.getenv("REPSY_PASSWORD")
            }
        }
    }
    publications {
        create<MavenPublication>("repsy") {
            groupId = project.group.toString()
            artifactId = "CHIMERA"
            version = project.version.toString()
            artifact(packZip)
        }
    }
}

tasks.named("publish") {
    dependsOn(packZip)
}

tasks.named("publishToMavenLocal") {
    dependsOn(packZip)
}
