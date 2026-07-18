<?php
/**
 * Theme functions for ZWD Portfolio.
 *
 * The initial block-theme structure is informed by the GPL-licensed Ollie theme.
 *
 * @package ZWD_Portfolio
 */

namespace ZWD_Portfolio;

function setup(): void {
	add_editor_style( 'style.css' );
	add_theme_support( 'wp-block-styles' );
	add_theme_support( 'responsive-embeds' );
	add_theme_support( 'editor-styles' );
	add_theme_support( 'post-thumbnails' );
}
add_action( 'after_setup_theme', __NAMESPACE__ . '\\setup' );

function enqueue_styles(): void {
	$stylesheet_path = get_stylesheet_directory() . '/style.css';
	wp_enqueue_style(
		'zwd-portfolio',
		get_stylesheet_uri(),
		array(),
		(string) filemtime( $stylesheet_path )
	);

	if ( is_front_page() ) {
		$build_dir = get_template_directory() . '/assets/build/';
		wp_enqueue_style(
			'zwd-portfolio-homepage',
			get_template_directory_uri() . '/assets/build/homepage.css',
			array( 'zwd-portfolio' ),
			(string) filemtime( $build_dir . 'homepage.css' )
		);
		wp_enqueue_script(
			'zwd-portfolio-homepage',
			get_template_directory_uri() . '/assets/build/homepage.js',
			array( 'wp-element' ),
			(string) filemtime( $build_dir . 'homepage.js' ),
			true
		);
		$rag_endpoint = defined( 'ZWD_RAG_PUBLIC_URL' )
			? (string) constant( 'ZWD_RAG_PUBLIC_URL' )
			: home_url( '/public/ask' );
		wp_add_inline_script(
			'zwd-portfolio-homepage',
			'window.zwdHomepageConfig = ' . wp_json_encode(
				array(
					'askUrl'   => esc_url_raw( $rag_endpoint ),
					'timeoutMs' => 30000,
				)
			) . ';',
			'before'
		);
	}

	if ( is_page( 'about' ) ) {
		$build_dir = get_template_directory() . '/assets/build/';
		wp_enqueue_style(
			'zwd-portfolio-about',
			get_template_directory_uri() . '/assets/build/about.css',
			array( 'zwd-portfolio' ),
			(string) filemtime( $build_dir . 'about.css' )
		);
	}

	if ( is_post_type_archive( 'project' ) ) {
		$build_dir = get_template_directory() . '/assets/build/';
		wp_enqueue_script(
			'zwd-project-carousel',
			get_template_directory_uri() . '/assets/build/project-carousel.js',
			array(),
			file_exists( $build_dir . 'project-carousel.js' )
				? (string) filemtime( $build_dir . 'project-carousel.js' )
				: time(),
			true
		);
	}
}
add_action( 'wp_enqueue_scripts', __NAMESPACE__ . '\\enqueue_styles' );

function register_pattern_category(): void {
	register_block_pattern_category(
		'zwd-portfolio',
		array( 'label' => __( '钟伟达作品集', 'zwd-portfolio' ) )
	);
}
add_action( 'init', __NAMESPACE__ . '\\register_pattern_category' );
