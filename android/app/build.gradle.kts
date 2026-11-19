plugins {
  alias(libs.plugins.android.application)
  alias(libs.plugins.compose.compiler)
  alias(libs.plugins.kotlin.serialization)
}

android {
  namespace = "com.atbm.app"
  compileSdk = 36
  defaultConfig {
    applicationId = "com.atbm.app"
    // Địa chỉ máy chủ mặc định của app (bắt buộc https://). Khi triển khai thật:
    //   ./gradlew assembleRelease -Patbm.serverUrl=https://api.ten-mien-cua-ban.vn/
    // Mặc định: backend local chạy bằng `./dev.sh run-https`, nhìn từ Android Emulator.
    val serverUrl = (project.findProperty("atbm.serverUrl") as String?) ?: "https://10.0.2.2:8443/"
    require(serverUrl.startsWith("https://")) { "atbm.serverUrl phải bắt đầu bằng https://" }
    buildConfigField("String", "SERVER_URL", "\"$serverUrl\"")
    minSdk = 26
    targetSdk = 36
    versionCode = 1
    versionName = "1.0"
  }

  buildTypes {
    release {
      isMinifyEnabled = false
      proguardFiles(getDefaultProguardFile("proguard-android-optimize.txt"), "proguard-rules.pro")
    }
  }
  compileOptions {
    sourceCompatibility = JavaVersion.VERSION_17
    targetCompatibility = JavaVersion.VERSION_17
  }
  buildFeatures {
    compose = true
    aidl = false
    buildConfig = true
    shaders = false
  }

  packaging {
    resources {
      excludes += "/META-INF/{AL2.0,LGPL2.1}"
    }
  }
}

kotlin {
  jvmToolchain(17)
}

dependencies {
  val composeBom = platform(libs.androidx.compose.bom)
  implementation(composeBom)
  androidTestImplementation(composeBom)

  // Core Android dependencies
  implementation(libs.androidx.core.ktx)
  implementation(libs.androidx.lifecycle.runtime.ktx)
  implementation(libs.androidx.activity.compose)

  // Arch Components
  implementation(libs.androidx.lifecycle.runtime.compose)
  implementation(libs.androidx.lifecycle.viewmodel.compose)

  // Compose
  implementation(libs.androidx.compose.ui)
  implementation(libs.androidx.compose.ui.tooling.preview)
  implementation(libs.androidx.compose.material3)
  implementation(libs.androidx.compose.material.icons)
  // Tooling
  debugImplementation(libs.androidx.compose.ui.tooling)
  // Instrumented tests
  androidTestImplementation(libs.androidx.compose.ui.test.junit4)
  debugImplementation(libs.androidx.compose.ui.test.manifest)

  // Local tests: jUnit, coroutines, Android runner
  testImplementation(libs.junit)
  testImplementation(libs.kotlinx.coroutines.test)

  // Instrumented tests: jUnit rules and runners
  androidTestImplementation(libs.androidx.test.core)
  androidTestImplementation(libs.androidx.test.ext.junit)
  androidTestImplementation(libs.androidx.test.runner)
  androidTestImplementation(libs.androidx.test.espresso.core)

  // Navigation
  implementation(libs.androidx.navigation3.ui)
  implementation(libs.androidx.navigation3.runtime)
  implementation(libs.androidx.lifecycle.viewmodel.navigation3)

  // Mạng & API
  implementation(libs.retrofit.core)
  implementation(libs.retrofit.converter.gson)
  implementation(libs.okhttp.core)
  implementation(libs.okhttp.logging)

  // Bảo mật & CSDL Mã hóa SQLCipher
  implementation(libs.sqlcipher.android)
  implementation(libs.androidx.sqlite.ktx)
  implementation(libs.androidx.biometric)
  implementation(libs.androidx.security.crypto)
}

// Bộ dữ liệu kiểm thử giao thức dùng chung với server (protocol/test_vectors.json, ngoài module):
// khai báo là input để Gradle chạy lại unit test mỗi khi file này thay đổi.
tasks.withType<Test>().configureEach {
  inputs.file(rootProject.file("../protocol/test_vectors.json"))
}
