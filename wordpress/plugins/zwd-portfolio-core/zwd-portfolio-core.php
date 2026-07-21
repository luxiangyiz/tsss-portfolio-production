<?php
/**
 * Plugin Name: ZWD Portfolio Core
 * Description: 注册项目内容类型、初始化公开求职内容并执行隐私验收。
 * Version: 1.0.0
 * Requires at least: 7.0
 * Requires PHP: 8.1
 * Author: 钟伟达
 * License: GPLv2 or later
 * Text Domain: zwd-portfolio-core
 *
 * @package ZWD_Portfolio_Core
 */

namespace ZWD_Portfolio_Core;

if ( ! defined( 'ABSPATH' ) ) {
	exit;
}

const VERSION = '2.1.0';

function register_content_types(): void {
	register_post_type(
		'project',
		array(
			'labels' => array(
				'name'          => '项目',
				'singular_name' => '项目',
				'add_new_item'  => '添加项目',
				'edit_item'     => '编辑项目',
				'view_item'     => '查看项目',
				'all_items'     => '全部项目',
			),
			'public'              => true,
			'show_ui'             => true,
			'show_in_menu'        => true,
			'has_archive'         => false,
			'rewrite'             => array(
				'slug'       => 'projects',
				'with_front' => false,
			),
			'menu_icon'           => 'dashicons-portfolio',
			'menu_position'       => 20,
			'show_in_rest'        => true,
			'supports'            => array( 'title', 'editor', 'excerpt', 'thumbnail', 'revisions', 'page-attributes' ),
			'publicly_queryable'  => true,
			'exclude_from_search' => true,
			'show_in_nav_menus'   => false,
		)
	);

	register_taxonomy(
		'project_skill',
		array( 'project' ),
		array(
			'labels' => array(
				'name'          => '项目技能',
				'singular_name' => '项目技能',
			),
			'public'            => false,
			'show_ui'           => true,
			'hierarchical'      => false,
			'show_in_rest'      => true,
			'show_admin_column' => true,
			'rewrite'           => false,
		)
	);

	foreach ( array( '_zwd_source_id', '_zwd_source_path', '_zwd_source_updated_at', '_zwd_project_role_summary' ) as $meta_key ) {
		register_post_meta(
			'project',
			$meta_key,
			array(
				'type'              => 'string',
				'single'            => true,
				'show_in_rest'      => false,
				'sanitize_callback' => 'sanitize_text_field',
				'auth_callback'     => static fn(): bool => current_user_can( 'edit_posts' ),
			)
		);
	}
}
add_action( 'init', __NAMESPACE__ . '\\register_content_types' );

function redirect_retired_routes(): void {
	global $wp;

	$path   = trim( (string) ( $wp->request ?? '' ), '/' );
	$target = '';
	$map    = array(
		'about'    => 'about',
		'resume'   => 'resume',
		'contact'  => 'contact',
		'projects' => 'projects',
	);

	if ( isset( $map[ $path ] ) ) {
		$target = $map[ $path ];
	} elseif ( str_starts_with( $path, 'project-skill/' ) ) {
		$target = 'projects';
	}

	if ( '' !== $target ) {
		wp_safe_redirect( home_url( '/#' . $target ), 301 );
		exit;
	}
}
add_action( 'template_redirect', __NAMESPACE__ . '\\redirect_retired_routes', 1 );

function disable_discussion_support(): void {
	foreach ( array( 'post', 'page', 'project' ) as $post_type ) {
		remove_post_type_support( $post_type, 'comments' );
		remove_post_type_support( $post_type, 'trackbacks' );
	}
}
add_action( 'init', __NAMESPACE__ . '\\disable_discussion_support', 20 );
add_filter( 'comments_open', '__return_false', 20 );
add_filter( 'pings_open', '__return_false', 20 );
add_filter( 'wpcf7_load_css', '__return_false' );
add_filter( 'wpcf7_load_js', '__return_false' );

function local_robots( array $robots ): array {
	if ( 'production' !== wp_get_environment_type() ) {
		$robots['noindex']  = true;
		$robots['nofollow'] = true;
		unset( $robots['index'], $robots['follow'] );
	}

	return $robots;
}
add_filter( 'wp_robots', __NAMESPACE__ . '\\local_robots' );

function project_role_shortcode(): string {
	$role = get_post_meta( get_the_ID(), '_zwd_project_role_summary', true );
	if ( ! is_string( $role ) || '' === trim( $role ) ) {
		return '';
	}

	return '<p class="project-card__role"><span>职责</span>' . esc_html( $role ) . '</p>';
}
add_shortcode( 'zwd_project_role', __NAMESPACE__ . '\\project_role_shortcode' );

function activate(): void {
	register_content_types();
	update_option( 'blog_public', '0' );
	update_option( 'default_comment_status', 'closed' );
	update_option( 'default_ping_status', 'closed' );
	flush_rewrite_rules();
}
register_activation_hook( __FILE__, __NAMESPACE__ . '\\activate' );

function source_root(): string {
	return WP_CONTENT_DIR . '/zwd-public-sources';
}

function read_approved_source( string $relative_path, string $expected_id ): array {
	$relative_path = ltrim( str_replace( '\\', '/', $relative_path ), '/' );
	$file_path     = source_root() . '/' . $relative_path;
	$real_root     = realpath( source_root() );
	$real_file     = realpath( $file_path );

	if ( false === $real_root || false === $real_file || ! str_starts_with( $real_file, $real_root . DIRECTORY_SEPARATOR ) ) {
		throw new \RuntimeException( '公开资料文件不存在或路径越界：' . $relative_path );
	}

	$contents = file_get_contents( $real_file );
	if ( false === $contents || ! preg_match( '/^---\s*(.*?)\s*---/s', $contents, $matches ) ) {
		throw new \RuntimeException( '公开资料缺少 YAML 头：' . $relative_path );
	}

	$frontmatter = array();
	foreach ( preg_split( '/\R/', trim( $matches[1] ) ) as $line ) {
		if ( preg_match( '/^([a-zA-Z0-9_]+):\s*(.*)$/', $line, $pair ) ) {
			$frontmatter[ $pair[1] ] = trim( $pair[2], " \t\n\r\0\x0B\"'" );
		}
	}

	$required = array(
		'id'                  => $expected_id,
		'privacy_level'       => 'public',
		'publish_status'      => 'published',
		'review_status'       => 'approved',
		'verification_status' => 'verified',
	);

	foreach ( $required as $key => $expected_value ) {
		if ( ( $frontmatter[ $key ] ?? '' ) !== $expected_value ) {
			throw new \RuntimeException( sprintf( '公开资料未通过发布门禁：%s（%s）', $relative_path, $key ) );
		}
	}

	return array(
		'id'         => $expected_id,
		'path'       => $relative_path,
		'updated_at' => $frontmatter['updated_at'] ?? '',
		'contents'   => $contents,
	);
}

function upsert_post( array $post_data, array $meta = array() ): int {
	$post_type = $post_data['post_type'];
	$slug      = $post_data['post_name'];
	$existing  = get_page_by_path( $slug, OBJECT, $post_type );

	if ( $existing instanceof \WP_Post ) {
		$post_data['ID'] = $existing->ID;
		$post_id         = wp_update_post( wp_slash( $post_data ), true );
	} else {
		$post_id = wp_insert_post( wp_slash( $post_data ), true );
	}

	if ( is_wp_error( $post_id ) ) {
		throw new \RuntimeException( $post_id->get_error_message() );
	}

	foreach ( $meta as $key => $value ) {
		update_post_meta( $post_id, $key, $value );
	}

	return (int) $post_id;
}

function seed_contact_form(): int {
	if ( ! post_type_exists( 'wpcf7_contact_form' ) ) {
		return 0;
	}

	$existing = get_page_by_path( 'recruitment-contact', OBJECT, 'wpcf7_contact_form' );
	$form_id  = upsert_post(
		array(
			'post_type'    => 'wpcf7_contact_form',
			'post_status'  => 'publish',
			'post_title'   => '招聘与合作联系',
			'post_name'    => 'recruitment-contact',
			'post_content' => '',
		)
	);

	$form = <<<'FORM'
<div class="contact-form">
<div class="contact-form__row">
<p><label>姓名（必填）[text* your-name autocomplete:name maxlength:80]</label></p>
<p><label>所在组织[email organization maxlength:120]</label></p>
</div>
<div class="contact-form__row">
<p><label>回复邮箱（必填）[email* reply-email autocomplete:email maxlength:160]</label></p>
<p><label>联系事项（必填）[select* subject "招聘机会" "项目合作" "技术交流" "其他"]</label></p>
</div>
<p><label>消息（必填）[textarea* message maxlength:2000]</label></p>
<p>[acceptance privacy-consent] 我已阅读<a href="/privacy/">隐私说明</a>，同意网站仅为回复本次联系而处理上述信息。 [/acceptance]</p>
<p>[submit "发送消息"]</p>
</div>
FORM;

	$mail = array(
		'active'             => true,
		'subject'            => '[_site_title] 联系表单：[subject]',
		'sender'             => '[_site_title] <wordpress@[_site_domain]>',
		'recipient'          => '[_site_admin_email]',
		'body'               => "姓名：[your-name]\n组织：[organization]\n回复邮箱：[reply-email]\n事项：[subject]\n\n[message]",
		'additional_headers' => 'Reply-To: [reply-email]',
		'attachments'        => '',
		'use_html'           => false,
		'exclude_blank'      => true,
	);

	update_post_meta( $form_id, '_form', $form );
	update_post_meta( $form_id, '_mail', $mail );
	update_post_meta( $form_id, '_mail_2', array( 'active' => false ) );
	update_post_meta( $form_id, '_messages', array() );
	update_post_meta( $form_id, '_additional_settings', '' );
	update_post_meta( $form_id, '_locale', 'zh_CN' );

	if ( $existing instanceof \WP_Post && $existing->ID !== $form_id ) {
		wp_delete_post( $existing->ID, true );
	}

	return $form_id;
}

function cleanup_starter_content(): void {
	$starter_titles = array(
		'page'               => array( 'Sample Page', 'Privacy Policy' ),
		'post'               => array( 'Hello world!' ),
		'wpcf7_contact_form' => array( 'Contact form 1' ),
	);

	foreach ( $starter_titles as $post_type => $titles ) {
		$posts = get_posts(
			array(
				'post_type'      => $post_type,
				'post_status'    => 'any',
				'posts_per_page' => -1,
			)
		);

		foreach ( $posts as $post ) {
			if ( in_array( $post->post_title, $titles, true ) ) {
				wp_delete_post( $post->ID, true );
			}
		}
	}
}

function render_project_gallery(): string {
	$projects = get_posts(
		array(
			'post_type'      => 'project',
			'post_status'    => 'publish',
			'posts_per_page' => -1,
			'orderby'        => array( 'menu_order' => 'ASC', 'date' => 'DESC' ),
		)
	);

	if ( empty( $projects ) ) {
		return '<p class="zwd-project-empty">项目资料正在整理中。</p>';
	}

	ob_start();
	?>
	<div class="zwd-project-gallery" data-project-carousel>
		<div class="zwd-projects__head zwd-frame">
			<div>
				<p class="zwd-kicker">02 / Selected work</p>
				<h2 class="zwd-section-title">项目</h2>
			</div>
			<div>
				<div class="zwd-project-controls" aria-label="项目卡片控制">
					<button class="zwd-project-control" type="button" data-project-previous aria-label="上一个项目">←</button>
					<button class="zwd-project-control" type="button" data-project-next aria-label="下一个项目">→</button>
				</div>
			</div>
		</div>
		<div class="zwd-project-track" data-project-track aria-label="项目卡片">
			<?php foreach ( $projects as $index => $project ) : ?>
				<?php
				$skills = wp_get_post_terms( $project->ID, 'project_skill' );
				$role   = (string) get_post_meta( $project->ID, '_zwd_project_role_summary', true );
				$slug   = $project->post_name;
				?>
				<a class="zwd-project-card" href="<?php echo esc_url( get_permalink( $project ) ); ?>" data-project-card="<?php echo esc_attr( $slug ); ?>" draggable="false">
					<span class="zwd-project-card__number"><?php echo esc_html( str_pad( (string) ( $index + 1 ), 2, '0', STR_PAD_LEFT ) ); ?></span>
					<span class="zwd-project-card__art" aria-hidden="true"></span>
					<span class="zwd-project-card__body">
						<span class="zwd-project-card__eyebrow"><?php echo esc_html( '' !== $role ? $role : 'AI 应用实践' ); ?></span>
						<h3><?php echo esc_html( $project->post_title ); ?></h3>
						<span class="zwd-project-card__excerpt"><?php echo esc_html( wp_trim_words( $project->post_excerpt, 52, '…' ) ); ?></span>
						<?php if ( ! is_wp_error( $skills ) && ! empty( $skills ) ) : ?>
							<span class="zwd-project-tags">
								<?php foreach ( $skills as $skill ) : ?><span><?php echo esc_html( $skill->name ); ?></span><?php endforeach; ?>
							</span>
						<?php endif; ?>
						<span class="zwd-project-card__cta">查看项目详情 →</span>
					</span>
				</a>
			<?php endforeach; ?>
		</div>
	</div>
	<?php
	return (string) ob_get_clean();
}
add_shortcode( 'zwd_project_gallery', __NAMESPACE__ . '\\render_project_gallery' );

function home_content(): string {
	return <<<'BLOCKS'
<!-- wp:html -->
<section class="zwd-section zwd-hero" id="top" aria-labelledby="zwd-home-title">
  <div class="zwd-frame zwd-hero__frame">
    <div class="zwd-hero__copy">
      <p class="zwd-hero__meta">PORTFOLIO <span>/ 2026</span></p>
      <h1 id="zwd-home-title">钟伟达<span>.</span></h1>
    </div>
    <div class="zwd-hero__stage">
      <div class="zwd-assistant-card">
        <div class="zwd-assistant-card__head">
          <span class="zwd-bot-mark" aria-hidden="true">AI</span>
          <div>
            <h2>你好，我是钟伟达的 AI 助手</h2>
            <p class="zwd-assistant-card__lead">你可以问我关于项目、经历和能力的问题</p>
          </div>
        </div>
        <div data-zwd-rag>
          <form class="zwd-rag-form" action="/public/ask" method="post">
            <label class="screen-reader-text" for="zwd-rag-question-static">向个人助手提问</label>
            <input id="zwd-rag-question-static" name="question" placeholder="问任何关于钟伟达的问题…" maxlength="500">
            <button type="submit">发送</button>
          </form>
          <p class="zwd-rag-privacy">AI 回答仅基于已审核的公开资料</p>
        </div>
      </div>
      <div class="zwd-hero__visual">
        <p class="zwd-hero__role"><strong>AI 应用交付</strong><span>/ FDE</span></p>
        <img class="zwd-hero__portrait" src="/wp-content/themes/zwd-portfolio/assets/images/hero-portrait.png" alt="钟伟达手绘人物形象" width="1024" height="1536" fetchpriority="high">
      </div>
    </div>
  </div>
</section>
<!-- /wp:html -->

<!-- wp:group {"align":"full","className":"zwd-section zwd-projects","anchor":"projects","layout":{"type":"default"}} -->
<section class="wp-block-group alignfull zwd-section zwd-projects" id="projects">
  <!-- wp:shortcode -->[zwd_project_gallery]<!-- /wp:shortcode -->
</section>
<!-- /wp:group -->

<!-- wp:html -->
<section class="zwd-section zwd-about" id="about" aria-labelledby="zwd-about-title">
  <div class="zwd-frame">
    <div class="zwd-about__head">
      <p class="zwd-kicker">03 / About</p>
      <h2 id="zwd-about-title"><span>从工程现场到</span><span>AI 应用交付</span></h2>
    </div>
    <div class="zwd-about__story">
      <p class="zwd-about__lead">我把工程领域形成的结构化分析、流程执行与质量意识，迁移到 AI 应用交付和知识库建设中。</p>
      <div class="zwd-about__detail">
        <p>我在莆田学院完成土木工程本科学习，并在厦门特房建工参与主体结构施工管理、工序检查和工程资料整理。现场经历让我习惯先明确目标与边界，再按流程推进，并持续关注质量与验收。</p>
        <p>现在我重点投入 RAG 知识库、AI 工具应用与面向真实需求的项目交付，希望把复杂技术转化为能被使用、验证和持续改进的解决方案。</p>
      </div>
    </div>
    <div class="zwd-capabilities">
      <article class="zwd-capability"><span>01</span><h3>结构化分析</h3><p>将复杂问题拆解为可验证的环节。</p></article>
      <article class="zwd-capability"><span>02</span><h3>流程与质量</h3><p>关注规范、边界、检查与验收标准。</p></article>
      <article class="zwd-capability"><span>03</span><h3>RAG 与知识库</h3><p>实践资料治理、检索问答、引用与隐私隔离。</p></article>
      <article class="zwd-capability"><span>04</span><h3>持续交付</h3><p>用可运行项目和可复核证据验证方案。</p></article>
    </div>
  </div>
</section>

<section class="zwd-section zwd-resume" id="resume" aria-labelledby="zwd-resume-title">
  <div class="zwd-frame">
    <div class="zwd-resume__head">
      <div><p class="zwd-kicker">04 / Resume</p><h2 class="zwd-section-title" id="zwd-resume-title">简历</h2></div>
      <p>2026 届本科，目标方向为 AI 应用交付、FDE 与 Agent 开发；意向厦门，也可考虑合适的异地机会。</p>
    </div>
    <div class="zwd-resume__grid">
      <div>
        <p class="zwd-resume__label">EXPERIENCE</p>
        <article><time>2024.06—2024.08</time><h3>施工员助理 · 厦门特房建工</h3><p>参与主体结构施工管理、工序检查、安全巡查、专项方案协作和工程资料整理，形成风险识别与闭环意识。</p></article>
        <p class="zwd-resume__label">PROJECT PRACTICE</p>
        <article><h3>个人求职知识库问答系统</h3><p>Markdown 资料治理、分层索引、增量更新、检索问答、引用与隐私隔离。</p></article>
        <article><h3>世界杯百科智能问答 BOT</h3><p>Dify 知识库配置、资料预处理、检索策略、Prompt 优化和多场景问答调试。</p></article>
      </div>
      <aside class="zwd-resume__side">
        <section><p class="zwd-resume__label">EDUCATION</p><h3>莆田学院</h3><p>土木工程 · 全日制本科<br>2022.09—2026.06</p></section>
        <section><p class="zwd-resume__label">AI APPLICATION</p><p>RAG、Dify、Prompt Engineering、FastAPI、LangChain、Qdrant</p></section>
        <section><p class="zwd-resume__label">WORKING STYLE</p><p>结构化分析 · 重视落地 · 过程清晰 · 持续学习</p></section>
      </aside>
    </div>
  </div>
</section>

<section class="zwd-section zwd-contact" id="contact" aria-labelledby="zwd-contact-title">
  <div class="zwd-frame">
    <p class="zwd-kicker">05 / Contact</p>
    <h2 class="zwd-contact__title" id="zwd-contact-title">一起把 AI 做到<strong>真实场景</strong>里？</h2>
    <div class="zwd-contact-list" aria-label="联系方式">
      <div class="zwd-contact-item"><span>01</span><div><small>微信号</small><strong>Tsss9318</strong></div></div>
      <a class="zwd-contact-item" href="tel:15059779318"><span>02</span><div><small>手机号</small><strong>15059779318</strong></div><span>拨打 →</span></a>
      <a class="zwd-contact-item" href="mailto:15059779318@163.com"><span>03</span><div><small>邮箱</small><strong>15059779318@163.com</strong></div><span>写邮件 →</span></a>
      <a class="zwd-contact-item" href="https://github.com/luxiangyiz/tsss-portfolio-production" target="_blank" rel="noopener noreferrer"><span>04</span><div><small>GitHub</small><strong>luxiangyiz/tsss-portfolio-production</strong></div><span>查看 →</span></a>
    </div>
    <div class="zwd-footer-line"><span>招聘机会 / 项目合作 / 技术交流</span><span>© 2026 钟伟达 · <a href="/privacy/">隐私说明</a></span></div>
  </div>
</section>
<!-- /wp:html -->
BLOCKS;
}

function legacy_home_content(): string {
	return <<<'BLOCKS'
<!-- wp:html -->
<section class="zwd-home-screen zwd-intro" aria-labelledby="zwd-home-title">
  <div>
    <h1 id="zwd-home-title"><span data-zwd-shiny>欢迎来到我的网站</span></h1>
    <p class="zwd-intro__role">钟伟达 · AI 应用交付 / FDE</p>
  </div>
</section>

<section class="zwd-home-screen zwd-assistant" aria-labelledby="zwd-assistant-title">
  <div class="zwd-prism" data-zwd-prism aria-hidden="true"></div>
  <div class="zwd-assistant__content">
    <h2 id="zwd-assistant-title">我是钟伟达的个人助手<span>你可以与我交谈，也可自行探索</span></h2>
    <p class="zwd-assistant__lead">了解我的经历、项目与能力</p>
    <div data-zwd-rag>
      <form class="zwd-rag-form" action="/public/ask" method="post">
        <label class="screen-reader-text" for="zwd-rag-question-static">向个人助手提问</label>
        <input id="zwd-rag-question-static" name="question" placeholder="问我任何关于经历、项目或能力的问题…" maxlength="500">
        <button type="submit">发送</button>
      </form>
      <p class="zwd-rag-privacy">AI 回答仅基于已审核的公开资料</p>
    </div>
  </div>
</section>

<section class="zwd-home-screen zwd-gallery-screen" aria-label="页面导航">
  <div data-zwd-gallery></div>
  <nav class="zwd-home-static-gallery" aria-label="页面导航备用链接">
    <a href="/about/">01 关于我 · 滑动探索 →</a>
    <a href="/projects/">02 项目</a>
    <a href="/resume/">03 简历</a>
    <a href="/contact/">04 联系方式</a>
  </nav>
</section>
<!-- /wp:html -->
BLOCKS;

	return <<<'BLOCKS'
<!-- wp:group {"align":"wide","className":"hero site-shell","layout":{"type":"constrained"}} -->
<div class="wp-block-group alignwide hero site-shell">
  <!-- wp:paragraph {"className":"section-kicker"} --><p class="section-kicker">Portfolio · 2026</p><!-- /wp:paragraph -->
  <!-- wp:heading {"level":1,"className":"hero__name"} --><h1 class="wp-block-heading hero__name">钟伟达</h1><!-- /wp:heading -->
  <!-- wp:heading {"level":2,"className":"hero__role"} --><h2 class="wp-block-heading hero__role">AI 应用交付 / FDE</h2><!-- /wp:heading -->
  <!-- wp:paragraph {"className":"hero__lead"} --><p class="hero__lead">从工程现场到 AI 应用，用结构化思维推动方案落地。关注知识库建设、AI 工具应用、质量验证和项目交付。</p><!-- /wp:paragraph -->
  <!-- wp:buttons --><div class="wp-block-buttons">
    <!-- wp:button --><div class="wp-block-button"><a class="wp-block-button__link wp-element-button" href="/projects/">查看项目</a></div><!-- /wp:button -->
    <!-- wp:button {"className":"is-style-outline"} --><div class="wp-block-button is-style-outline"><a class="wp-block-button__link wp-element-button" href="/contact/">联系我</a></div><!-- /wp:button -->
  </div><!-- /wp:buttons -->
</div>
<!-- /wp:group -->

<!-- wp:group {"align":"wide","className":"editorial-section site-shell","layout":{"type":"constrained"}} -->
<div class="wp-block-group alignwide editorial-section site-shell">
  <!-- wp:paragraph {"className":"section-kicker"} --><p class="section-kicker">Capabilities</p><!-- /wp:paragraph -->
  <!-- wp:heading {"level":2} --><h2 class="wp-block-heading">核心能力</h2><!-- /wp:heading -->
  <!-- wp:columns {"className":"capability-grid"} --><div class="wp-block-columns capability-grid">
    <!-- wp:column --><div class="wp-block-column"><p class="capability-index">01</p><h3>需求分析与方案设计</h3><p>从业务目标出发，梳理需求、边界与可验证的交付标准。</p></div><!-- /wp:column -->
    <!-- wp:column --><div class="wp-block-column"><p class="capability-index">02</p><h3>RAG 与知识库</h3><p>具备资料整理、切片、检索配置、隐私分级和引用问答实践。</p></div><!-- /wp:column -->
    <!-- wp:column --><div class="wp-block-column"><p class="capability-index">03</p><h3>AI 工具应用</h3><p>持续使用 Dify、Codex 等工具推进应用配置、开发和测试。</p></div><!-- /wp:column -->
    <!-- wp:column --><div class="wp-block-column"><p class="capability-index">04</p><h3>工程化与质量意识</h3><p>关注流程执行、风险识别、资料规范、测试与验收。</p></div><!-- /wp:column -->
  </div><!-- /wp:columns -->
</div>
<!-- /wp:group -->

<!-- wp:group {"align":"wide","className":"editorial-section site-shell","layout":{"type":"constrained"}} -->
<div class="wp-block-group alignwide editorial-section site-shell">
  <!-- wp:paragraph {"className":"section-kicker"} --><p class="section-kicker">Selected Work</p><!-- /wp:paragraph -->
  <!-- wp:heading {"level":2} --><h2 class="wp-block-heading">精选项目</h2><!-- /wp:heading -->
  <!-- wp:query {"queryId":9,"query":{"perPage":2,"pages":0,"offset":0,"postType":"project","order":"asc","orderBy":"menu_order","author":"","search":"","exclude":[],"sticky":"","inherit":false}} -->
  <div class="wp-block-query"><!-- wp:post-template {"className":"project-card-grid featured-projects","layout":{"type":"default"}} -->
    <!-- wp:group {"className":"project-card","layout":{"type":"constrained"}} --><div class="wp-block-group project-card">
      <!-- wp:post-title {"isLink":true,"className":"project-card__title","fontSize":"x-large"} /-->
      <!-- wp:post-excerpt {"moreText":"","showMoreOnNewLine":false,"className":"project-card__excerpt"} /-->
      <!-- wp:paragraph {"className":"project-card__stack-label"} --><p class="project-card__stack-label">技术栈</p><!-- /wp:paragraph -->
      <!-- wp:post-terms {"term":"project_skill","separator":" "} /-->
      <!-- wp:paragraph {"className":"project-card__link"} --><p class="project-card__link">查看项目 →</p><!-- /wp:paragraph -->
    </div><!-- /wp:group -->
  <!-- /wp:post-template --></div>
  <!-- /wp:query -->
</div>
<!-- /wp:group -->

<!-- wp:group {"align":"wide","className":"editorial-section site-shell","layout":{"type":"constrained"}} -->
<div class="wp-block-group alignwide editorial-section site-shell">
  <!-- wp:paragraph {"className":"section-kicker"} --><p class="section-kicker">Transferable Skills</p><!-- /wp:paragraph -->
  <!-- wp:heading {"level":2} --><h2 class="wp-block-heading">能力迁移</h2><!-- /wp:heading -->
  <!-- wp:columns {"className":"transition-flow"} --><div class="wp-block-columns transition-flow">
    <!-- wp:column --><div class="wp-block-column"><h3>工程现场经验</h3><p>工序检查<br>风险排查<br>资料管理</p></div><!-- /wp:column -->
    <!-- wp:column --><div class="wp-block-column"><h3>工程化思维</h3><p>流程标准化<br>问题定位<br>质量验收</p></div><!-- /wp:column -->
    <!-- wp:column --><div class="wp-block-column"><h3>AI 领域能力</h3><p>知识库建设<br>模型与工具应用<br>测试与隐私隔离</p></div><!-- /wp:column -->
    <!-- wp:column --><div class="wp-block-column"><h3>交付价值</h3><p>理解业务问题<br>推动方案落地<br>持续复盘改进</p></div><!-- /wp:column -->
  </div><!-- /wp:columns -->
</div>
<!-- /wp:group -->

<!-- wp:group {"align":"wide","className":"editorial-section site-shell","layout":{"type":"constrained"}} -->
<div class="wp-block-group alignwide editorial-section site-shell">
  <!-- wp:columns {"verticalAlignment":"center"} --><div class="wp-block-columns are-vertically-aligned-center">
    <!-- wp:column {"verticalAlignment":"center","width":"70%"} --><div class="wp-block-column is-vertically-aligned-center" style="flex-basis:70%"><p class="section-kicker">Contact</p><h2>正在寻找 AI 应用交付与 FDE 方向的机会</h2><p>期待与重视实际价值、持续学习和项目落地的团队交流。</p></div><!-- /wp:column -->
    <!-- wp:column {"verticalAlignment":"center","width":"30%"} --><div class="wp-block-column is-vertically-aligned-center" style="flex-basis:30%"><div class="wp-block-buttons is-content-justification-right"><div class="wp-block-button is-style-outline"><a class="wp-block-button__link wp-element-button" href="/contact/">发送消息</a></div></div></div><!-- /wp:column -->
  </div><!-- /wp:columns -->
</div>
<!-- /wp:group -->
BLOCKS;
}

function about_content(): string {
	return <<<'BLOCKS'
<!-- wp:html -->
<div class="about-page">
  <section class="about-page-hero" aria-labelledby="about-page-title">
    <div class="about-page-hero__text">
      <p class="about-page-hero__kicker">ABOUT</p>
      <h1 class="about-page-hero__title" id="about-page-title">从工程现场，到 AI 应用交付</h1>
      <p class="about-page-hero__lead">把工程领域形成的结构化分析、流程执行与质量意识，迁移到 AI 应用交付和知识库建设中。</p>
    </div>
    <div class="about-page-photo" role="img" aria-label="抽象灰度人物照片占位"></div>
  </section>

  <section class="about-page-section about-page-transition">
    <div class="about-page-story">
      <h2 class="about-page-section-title">转型故事</h2>
      <p>我在莆田学院完成土木工程本科学习，并在厦门特房建工的施工员助理岗位上参与过主体结构施工管理、工序检查与工程资料整理。现场工作让我习惯用结构化的方式拆解问题：先明确目标与边界，再按流程推进，并在每个环节关注质量与验收。</p>
      <p>在项目实践与持续学习中，我把工程领域形成的分析方法、流程意识与质量观念，迁移到 AI 应用交付方向。我重点投入 RAG 知识库与 AI 工具应用，实践过基于 Dify 的世界杯主题问答，也参与构建面向个人求职场景的代码型 RAG 知识助手，目标是把可验证、可复盘的交付方式带到 AI 项目中。</p>
    </div>
    <div class="about-page-capability">
      <h2 class="about-page-section-title">能力迁移</h2>
      <ul class="about-page-capability-list">
        <li>结构化分析 — 将复杂问题拆解为可验证的环节</li>
        <li>流程执行 — 按既定步骤推进并保持交付</li>
        <li>质量意识 — 关注规范、检查与验收标准</li>
        <li>学习迁移 — 把既有经验迁移到新领域</li>
      </ul>
    </div>
  </section>

  <section class="about-page-section">
    <h2 class="about-page-section-title">教育与实习</h2>
    <div class="about-page-timeline">
      <div class="about-page-timeline-item">
        <p class="about-page-timeline-date">2022.09—2026.06</p>
        <span class="about-page-timeline-org">莆田学院 · 土木工程</span>
        <p class="about-page-timeline-desc">全日制本科，工学学士。学习经历形成了结构化分析、风险意识、流程管理、资源协调和方案落地的基础。</p>
      </div>
      <div class="about-page-timeline-item">
        <p class="about-page-timeline-date">2024.06—2024.08</p>
        <span class="about-page-timeline-org">厦门特房建工 · 施工员助理</span>
        <p class="about-page-timeline-desc">参与主体结构施工管理、工序检查、安全巡查、专项方案协作和工程资料整理。</p>
      </div>
    </div>
  </section>

  <section class="about-page-section">
    <h2 class="about-page-section-title">工作方式</h2>
    <div class="about-page-values">
      <div class="about-page-value-item">
        <div class="about-page-value-header">
          <svg class="about-page-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M8.5 12.5l2.5 2.5 4.5-5"/></svg>
          <h3>重视落地</h3>
        </div>
        <p>通过项目验证工具与方法，不把概念停留在描述层面。</p>
      </div>
      <div class="about-page-value-item">
        <div class="about-page-value-header">
          <svg class="about-page-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><circle cx="5" cy="12" r="2"/><circle cx="19" cy="12" r="2"/><path d="M7 12h10"/><path d="M14 9.5l2.5 2.5L14 14.5"/></svg>
          <h3>过程清晰</h3>
        </div>
        <p>关注资料规范、质量检查、风险边界和验收标准。</p>
      </div>
      <div class="about-page-value-item">
        <div class="about-page-value-header">
          <svg class="about-page-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M12 19V5"/><path d="M7 10l5-5 5 5"/></svg>
          <h3>持续学习</h3>
        </div>
        <p>长期关注 RAG、AI Agent 和主流 AI 开发工具。</p>
      </div>
    </div>
  </section>

  <section class="about-page-section">
    <h2 class="about-page-section-title">工作之外</h2>
    <div class="about-page-interests">
      <span class="about-page-interest-item"><svg class="about-page-icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M4 5h7v14H4zM20 5h-7v14h7z"/></svg>阅读</span>
      <span class="about-page-interest-item"><svg class="about-page-icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><circle cx="12" cy="12" r="9"/><path d="M12 8l3 2-1 4h-4l-1-4z"/></svg>足球</span>
      <span class="about-page-interest-item"><svg class="about-page-icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><rect x="3" y="7" width="18" height="12" rx="1"/><circle cx="12" cy="13" r="3.5"/><path d="M8 7l2-2h4l2 2"/></svg>摄影</span>
      <span class="about-page-interest-item"><svg class="about-page-icon-sm" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" aria-hidden="true"><path d="M4 20l4-1 11-11-3-3L5 16z"/><path d="M14 6l3 3"/></svg>写作</span>
    </div>
  </section>

  <section class="about-page-cta">
    <a href="/projects/">查看项目 →</a>
  </section>
</div>
<!-- /wp:html -->
BLOCKS;
}

function resume_content(): string {
	return <<<'BLOCKS'
<!-- wp:html -->
<main class="resume-page">
  <header class="resume-page-hero">
    <p class="resume-page-kicker">RESUME</p>
    <h1>公开简历</h1>
    <p class="resume-page-name">钟伟达</p>
    <p class="resume-page-lead">从工程现场转向 AI 应用实践，关注知识库建设、RAG 应用与面向真实需求的项目交付。</p>
  </header>

  <section class="resume-page-facts" aria-label="求职关键信息">
    <div><span>目标方向</span><strong>AI 应用交付 · FDE · Agent 开发</strong></div>
    <div><span>意向地点</span><strong>厦门 · 可考虑异地机会</strong></div>
    <div><span>当前状态</span><strong>2026 届本科 · 可随时到岗</strong></div>
  </section>

  <div class="resume-page-layout">
    <div class="resume-page-main">
      <section class="resume-page-section">
        <p class="resume-page-section-index">01 / PROFILE</p>
        <h2>个人简介</h2>
        <p>莆田学院土木工程专业本科毕业生，正在将工程领域形成的结构化分析、流程执行、风险识别和质量意识迁移到 AI 应用领域。已完成 Dify RAG 智能问答实践，并参与构建面向个人求职资料的代码型 RAG 知识库问答系统。</p>
        <p>重视从需求拆解、资料治理、方案实现到测试验收的完整链路，倾向于用可运行项目和可复核证据验证工具与方法。</p>
      </section>

      <section class="resume-page-section">
        <p class="resume-page-section-index">02 / EXPERIENCE</p>
        <h2>实习经历</h2>
        <article class="resume-page-entry">
          <div class="resume-page-entry-head">
            <div>
              <h3>施工员助理</h3>
              <p class="resume-page-org">厦门特房建工</p>
            </div>
            <time>2024.06—2024.08</time>
          </div>
          <ul>
            <li>参与主体结构施工管理与工序检查，协助核对现场执行情况和质量要求。</li>
            <li>参与安全巡查、专项方案协作与问题记录，形成风险识别和闭环意识。</li>
            <li>整理工程资料并配合多工序协作，积累资料规范化、流程推进与现场沟通经验。</li>
          </ul>
        </article>
      </section>

      <section class="resume-page-section">
        <p class="resume-page-section-index">03 / PROJECTS</p>
        <h2>项目经历</h2>

        <article class="resume-page-project">
          <div class="resume-page-project-head">
            <h3><a href="/projects/ai-job-rag-assistant/">个人求职知识库问答系统</a></h3>
            <span>代码型 RAG</span>
          </div>
          <p>面向教育经历、项目证据、岗位资料和复盘记录构建可持续更新的个人知识库，兼顾检索效果、内容可追溯性与公开访问边界。</p>
          <ul>
            <li>参与 Markdown 解析、结构化分块、全量建库与增量更新流程的设计、实现和测试。</li>
            <li>建立 private、internal、public 三层索引隔离，并验证公开接口无法越过隐私边界。</li>
            <li>实现基于检索证据的问答、来源引用与证据不足拒答，完成本地真实模型运行验收。</li>
          </ul>
          <div class="resume-page-tags"><span>FastAPI</span><span>LangChain</span><span>Qdrant</span><span>RAG</span></div>
        </article>

        <article class="resume-page-project">
          <div class="resume-page-project-head">
            <h3><a href="/projects/world-cup-rag-bot/">世界杯百科智能问答 BOT</a></h3>
            <span>Dify 应用</span>
          </div>
          <p>基于 Dify 与 RAG 搭建世界杯主题智能问答应用，实践从资料准备、知识库配置到应用调试和交付呈现的完整流程。</p>
          <ul>
            <li>整理并预处理主题资料，调整知识库切片方式和检索配置。</li>
            <li>迭代 Prompt 与回答约束，覆盖赛程、球队、球员、规则等多类问答场景。</li>
            <li>验证网页或公众号嵌入方式，理解从应用编排到用户访问入口的交付链路。</li>
          </ul>
          <div class="resume-page-tags"><span>Dify</span><span>Prompt Engineering</span><span>RAG</span></div>
        </article>
      </section>
    </div>

    <aside class="resume-page-side">
      <section class="resume-page-section">
        <p class="resume-page-section-index">04 / SKILLS</p>
        <h2>技能与工具</h2>
        <div class="resume-page-skill-group">
          <h3>AI 应用</h3>
          <p>RAG 知识库、Dify 应用配置、Prompt 优化、检索问答与知识库治理</p>
        </div>
        <div class="resume-page-skill-group">
          <h3>开发与数据</h3>
          <p>FastAPI、LangChain、Qdrant、Markdown、API；Python 与部署能力持续提升中</p>
        </div>
        <div class="resume-page-skill-group">
          <h3>AI 工具</h3>
          <p>Codex、Trae、Hermes、Claude Code</p>
        </div>
        <div class="resume-page-skill-group">
          <h3>工程能力</h3>
          <p>项目流程、质量检查、风险识别、资料管理与跨任务协作</p>
        </div>
      </section>

      <section class="resume-page-section">
        <p class="resume-page-section-index">05 / EDUCATION</p>
        <h2>教育背景</h2>
        <div class="resume-page-education">
          <time>2022.09—2026.06</time>
          <h3>莆田学院</h3>
          <p>土木工程 · 全日制本科<br>工学学士</p>
          <p class="resume-page-note">核心学习覆盖结构力学、工程项目管理、施工组织与规划、工程经济学、CAD 与 BIM 技术应用。</p>
        </div>
      </section>

      <section class="resume-page-section">
        <p class="resume-page-section-index">06 / STRENGTHS</p>
        <h2>能力特点</h2>
        <ul class="resume-page-strengths">
          <li><strong>结构化分析</strong><span>将复杂问题拆解为可验证环节</span></li>
          <li><strong>重视落地</strong><span>通过项目运行和验收验证方法</span></li>
          <li><strong>过程意识</strong><span>关注规范、边界、质量与复盘</span></li>
          <li><strong>学习迁移</strong><span>把工程经验迁移到 AI 交付</span></li>
        </ul>
      </section>
    </aside>
  </div>

  <footer class="resume-page-cta">
    <div>
      <p class="resume-page-section-index">CONTACT</p>
      <h2>期待参与真实 AI 应用的落地与交付</h2>
      <p>如有合适的岗位或合作机会，欢迎通过网站公开的联系方式联系。</p>
    </div>
    <a href="/contact/">联系我 <span aria-hidden="true">→</span></a>
  </footer>
</main>
<!-- /wp:html -->
BLOCKS;
}

function contact_content( int $form_id ): string {
	unset( $form_id );

	return <<<'BLOCKS'
<!-- wp:html -->
<main class="contact-page">
  <header class="contact-page-hero">
    <p class="contact-page-kicker">CONTACT</p>
    <h1>联系我</h1>
    <p>您可通过以下方式联系我：</p>
  </header>

  <section class="contact-page-list" aria-label="联系方式">
    <div class="contact-page-item">
      <span class="contact-page-index">01</span>
      <div>
        <p>微信号</p>
        <strong>Tsss9318</strong>
      </div>
    </div>
    <a class="contact-page-item" href="tel:15059779318">
      <span class="contact-page-index">02</span>
      <div>
        <p>手机号</p>
        <strong>15059779318</strong>
      </div>
      <span class="contact-page-action" aria-hidden="true">拨打 →</span>
    </a>
    <a class="contact-page-item" href="mailto:15059779318@163.com">
      <span class="contact-page-index">03</span>
      <div>
        <p>邮箱</p>
        <strong>15059779318@163.com</strong>
      </div>
      <span class="contact-page-action" aria-hidden="true">写邮件 →</span>
    </a>
    <a class="contact-page-item" href="https://github.com/luxiangyiz/tsss-portfolio-production" target="_blank" rel="noopener noreferrer">
      <span class="contact-page-index">04</span>
      <div>
        <p>GitHub 项目</p>
        <strong>github.com/luxiangyiz/tsss-portfolio-production</strong>
      </div>
      <span class="contact-page-action" aria-hidden="true">查看 →</span>
    </a>
  </section>

  <p class="contact-page-note">联系时请简单说明您的姓名、所在组织与沟通事项，我会在看到消息后尽快回复。</p>
</main>
<!-- /wp:html -->
BLOCKS;
}

function privacy_content(): string {
	return <<<'BLOCKS'
<!-- wp:group {"align":"wide","className":"page-hero site-shell","layout":{"type":"constrained"}} --><div class="wp-block-group alignwide page-hero site-shell"><p class="section-kicker">Privacy</p><h1>隐私说明</h1><p>本网站只展示经过审核的公开求职资料。</p></div><!-- /wp:group -->
<!-- wp:group {"align":"wide","className":"editorial-section site-shell","layout":{"type":"constrained"}} --><div class="wp-block-group alignwide editorial-section site-shell"><h2>公开联系方式</h2><p>联系页面展示的微信号、手机号与邮箱由本人明确授权公开，仅用于招聘、合作及相关事项沟通。</p><h2>不公开的信息</h2><p>除上述主动公开的联系方式外，网站不会公开身份资料、求职沟通记录、薪资信息、内部岗位资料和系统密钥。</p></div><!-- /wp:group -->
BLOCKS;
}

function project_content_world_cup(): string {
	return <<<'BLOCKS'
<!-- wp:heading {"level":2} --><h2>项目背景</h2><!-- /wp:heading -->
<!-- wp:paragraph --><p>世界杯相关信息覆盖赛程、球队、球员、历届赛果、赛事规则和比赛场馆等多个主题，资料来源分散，时间跨度也很长。用户如果依赖普通搜索，需要在不同页面之间反复查找；直接询问通用大模型，又可能遇到资料滞后、事实混淆或脱离来源作答的问题。</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p>这个项目使用 Dify 搭建世界杯百科智能问答 BOT，并配置专属 RAG 知识库，希望把分散资料整理为可检索的内容集合，再通过检索增强生成让模型优先依据知识库回答。项目重点不是制作一个固定问答列表，而是实践从资料处理、知识库配置到问答调试和应用发布的完整流程。</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":2} --><h2>问题与目标</h2><!-- /wp:heading -->
<!-- wp:list --><ul><li><strong>组织主题资料：</strong>对世界杯相关文档进行整理和预处理，使不同主题、不同格式的内容能够进入统一知识库。</li><li><strong>改善检索上下文：</strong>通过文档切片和检索配置，让系统能够找到与问题相关的资料片段，并把有效上下文交给模型生成回答。</li><li><strong>减少事实偏离：</strong>利用 RAG 约束回答依据，降低模型在赛事数据、历史结果和规则类问题上脱离资料自由生成的风险。</li><li><strong>覆盖多类问题：</strong>围绕赛程、球队战绩、球员信息、历届赛果、赛事规则和球场资料等场景进行问答调试，并关注连续追问时的上下文表现。</li><li><strong>验证交付方式：</strong>在 Dify 中完成应用编排，并验证通过网页或公众号嵌入方式向实际访问入口提供问答能力的可行性。</li></ul><!-- /wp:list -->
<!-- wp:heading {"level":2} --><h2>个人职责</h2><!-- /wp:heading -->
<!-- wp:list {"ordered":true} --><ol><li><strong>资料整理与预处理：</strong>梳理世界杯主题资料，处理不利于检索的排版和内容结构，为后续切片与入库做准备。</li><li><strong>知识库配置：</strong>在 Dify 中建立知识库，调整文档切片方式与检索设置，观察不同配置对召回内容和回答完整度的影响。</li><li><strong>Prompt 设计：</strong>编写并迭代问答提示词，明确回答范围、资料优先级和表达方式，减少模型偏离世界杯主题或忽略检索内容。</li><li><strong>场景调试：</strong>针对赛程、球队、球员、历史赛果、赛事规则和球场等不同类型的问题进行测试，并检查单轮回答和连续追问的表现。</li><li><strong>应用呈现：</strong>完成 Dify 应用编排，生成并验证网页或公众号嵌入方式，了解从知识库配置到用户访问入口的交付链路。</li></ol><!-- /wp:list -->
<!-- wp:heading {"level":2} --><h2>方案与技术栈</h2><!-- /wp:heading -->
<!-- wp:list --><ul><li><strong>Dify 应用编排：</strong>用于创建知识库、配置检索、连接大模型、组织对话流程，并提供应用调试和嵌入能力。</li><li><strong>RAG 检索增强生成：</strong>在生成回答前从世界杯专属资料中检索相关内容，让回答尽量建立在已有知识文档之上。</li><li><strong>Embedding 向量检索：</strong>把用户问题与知识分块转换为可比较的语义表示，用于召回主题相关的资料片段。</li><li><strong>知识库切片与检索策略：</strong>围绕段落完整性、主题边界和检索上下文调整分片与召回配置，减少信息被切断或无关内容混入。</li><li><strong>Prompt Engineering：</strong>约束回答角色、主题范围和回答方式，引导模型结合检索结果完成赛事信息问答和多轮追问。</li><li><strong>网页与公众号嵌入：</strong>验证 Dify 应用从配置界面走向用户入口的轻量化接入方式，为后续部署和展示积累经验。</li></ul><!-- /wp:list -->
<!-- wp:heading {"level":2} --><h2>成果与证据</h2><!-- /wp:heading -->
<!-- wp:list --><ul><li>完成世界杯主题资料的整理、预处理和知识库导入，形成可用于检索问答的内容基础。</li><li>完成 Dify 知识库、应用流程、检索策略和 Prompt 的组合配置，跑通从用户提问、资料召回到模型回答的基本链路。</li><li>覆盖赛程、球队、球员、历届赛果、赛事规则和球场信息等多类问答场景，并对连续追问进行调试。</li><li>验证网页或公众号嵌入方式，确认应用可以通过轻量入口向用户提供问答能力。</li><li>沉淀了资料质量、文档切片、检索结果和提示词之间相互影响的实践经验，为后续代码型 RAG 项目提供了基础。</li></ul><!-- /wp:list -->
<!-- wp:paragraph --><p>目前项目缺少可公开复核的标准测试集、原始测试结果和统一统计口径，因此不展示未经验证的准确率与响应时间数字。现阶段证据以经过审核的项目说明和实际配置流程为主。</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":2} --><h2>复盘</h2><!-- /wp:heading -->
<!-- wp:paragraph --><p>这个项目让我第一次完整理解 RAG 应用并不是“上传文档后直接提问”。资料本身的质量、切片是否保留完整语义、检索能否召回正确上下文、Prompt 是否真正使用检索结果，都会影响最终回答。Dify 降低了应用编排门槛，但效果判断仍然需要清晰的测试场景和持续调试。</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p>项目当前更能证明 Dify、RAG 知识库配置和 Prompt 调试的实践过程，还不能替代严格的效果评测。下一阶段需要补充固定问题集、失败案例、检索参数记录以及调优前后的对比结果，使回答质量能够被重复验证，而不是只依赖主观体验。</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":2} --><h2>公开链接</h2><!-- /wp:heading -->
<!-- wp:paragraph --><p>当前公开内容以经过审核的项目说明为主，Dify 应用截图、独立演示入口和相关配置记录仍在整理。由于现阶段还没有完成公开环境复核，不提供无法持续访问或缺少说明的临时链接。</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p>后续将在确认知识库资料可公开、应用配置不包含敏感信息，并完成基础问答回归测试后，再补充可复验的演示材料。</p><!-- /wp:paragraph -->
BLOCKS;
}

function project_content_job_rag(): string {
	return <<<'BLOCKS'
<!-- wp:heading {"level":2} --><h2>项目背景</h2><!-- /wp:heading -->
<!-- wp:paragraph --><p>个人求职过程中会持续产生教育经历、项目材料、技能证据、岗位信息、面试准备和阶段复盘等内容。它们原本分散在不同的 Markdown 文档中，既不便于统一维护，也难以在需要时快速找到可靠依据。</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p>这个项目将这些资料整理为可持续更新的个人知识库，并在此基础上构建检索与问答能力。系统不仅需要回答“我做过什么”，还要能够指出答案来自哪些资料、识别证据不足的情况，并保证个人网站只能访问经过审核的公开内容。</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":2} --><h2>问题与目标</h2><!-- /wp:heading -->
<!-- wp:list --><ul><li><strong>统一资料结构：</strong>解析带有 Front Matter 的 Markdown 文档，保留标题层级、来源、核实状态和隐私等级等信息，减少资料长期积累后的混乱。</li><li><strong>建立访问边界：</strong>按照 private、internal、public 三种范围分别组织索引，使私人资料、内部求职材料和网站公开内容进入不同的检索空间。</li><li><strong>支持持续更新：</strong>同时提供全量建库和增量更新能力，识别新增、修改、元数据变化与删除，避免每次内容调整都从头处理全部资料。</li><li><strong>提升回答可信度：</strong>要求回答基于检索证据并返回来源；当资料无法支持结论时明确提示证据不足，不用模型自由补全个人经历。</li><li><strong>服务网站展示：</strong>为个人网站提供独立的公开问答入口，让访问者能够在不接触私人知识库的前提下了解公开履历与项目信息。</li></ul><!-- /wp:list -->
<!-- wp:heading {"level":2} --><h2>个人职责</h2><!-- /wp:heading -->
<!-- wp:paragraph --><p>我负责从需求梳理到本地验收的完整实现过程，包括设计知识文档结构与元数据规范、划分三类隐私范围、实现 Markdown 扫描与解析、组织索引构建流程，并连接检索、问答和来源引用链路。</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p>在工程验证方面，我持续检查 Manifest 与 Qdrant 中索引状态的一致性，补充全量和增量更新场景，并通过公开范围测试确认网站问答无法检索 private 或 internal 内容。同时整理经过审核的公开候选资料，使知识库内容可以安全地接入个人网站。</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":2} --><h2>方案与技术栈</h2><!-- /wp:heading -->
<!-- wp:list --><ul><li><strong>FastAPI：</strong>提供服务健康检查、知识库预览、全量与增量入库、检索、问答以及公开问答接口，并为本地演示页面提供统一后端。</li><li><strong>LangChain：</strong>连接文档分块、Embedding、向量检索和对话模型，让通用 RAG 组件与项目自定义的隐私和更新规则协同工作。</li><li><strong>Qdrant：</strong>分别保存 private、internal、public 三类知识分块向量，并根据访问范围选择对应 Collection，避免只在回答生成阶段做隐私过滤。</li><li><strong>通义千问 text-embedding-v4：</strong>为知识分块生成 1536 维语义向量，用于真实模型模式下的相似度检索。</li><li><strong>DeepSeek：</strong>根据检索得到的证据组织回答，并与引用、证据不足拒答和公开范围提示共同构成回答链路。</li><li><strong>Manifest V2：</strong>按文档和访问范围记录内容哈希、元数据状态及分块索引信息，用于判断新增、修改、隐私变化和删除，并保持增量更新可追踪。</li><li><strong>本地演示模式：</strong>提供不依赖 API Key 的确定性 Fake Embedding 与 FakeChatModel，用于验证工程链路；真实模型模式则用于检查实际检索和生成效果，两者的验收目标明确区分。</li></ul><!-- /wp:list -->
<!-- wp:heading {"level":2} --><h2>成果与证据</h2><!-- /wp:heading -->
<!-- wp:list --><ul><li>实现知识库目录扫描、Front Matter 校验、Markdown 解析和按标题层级保留上下文的结构化分块。</li><li>实现全量建库与增量更新流程，能够处理新增、内容修改、元数据变化和删除，并记录各访问范围的处理结果。</li><li>建立 private、internal、public 三套索引及对应路由规则，使公开接口只能使用 public Collection。</li><li>完成基于检索证据的回答与来源引用，并在没有有效命中或证据无法支持结论时返回证据不足状态。</li><li>提供本地演示页面与自动验证脚本，可检查服务状态、知识库预览、索引统计、搜索、引用问答和无变化增量更新。</li><li>完成真实模型本地运行和公开范围隐私验收，验证涉及私人信息的问题不会通过 public 检索返回 private 或 internal 文档引用。</li><li>将经过审核的公开资料接入个人网站问答入口，同时保留本地知识库与网站公开内容之间的边界。</li></ul><!-- /wp:list -->
<!-- wp:heading {"level":2} --><h2>复盘</h2><!-- /wp:heading -->
<!-- wp:paragraph --><p>这个项目让我认识到，个人知识库并不是把文档放进向量数据库就结束了。资料是否经过核实、更新后能否同步、引用是否可追溯、不同访问者能看到什么，都会直接影响系统是否可信。相比单独追求一次回答效果，稳定的资料治理和安全边界更接近一个可以长期使用的交付成果。</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p>工程上最需要持续关注的是索引状态与真实数据的一致性，因此项目引入 Manifest V2 管理不同访问范围的更新状态，并把全量、增量、隐私变化和删除纳入验证流程。下一阶段仍需要基于固定测试集补充真实模型的 Recall、拒答质量和回答稳定性评估；在这些数据完成复核之前，不展示未经验证的准确率指标。</p><!-- /wp:paragraph -->
<!-- wp:heading {"level":2} --><h2>公开链接</h2><!-- /wp:heading -->
<!-- wp:paragraph --><p>当前项目以本地可运行系统、自动验证脚本、测试记录和个人网站中的公开问答入口作为阶段性成果。完整知识库包含私人及内部求职资料，因此不会直接对外发布。</p><!-- /wp:paragraph -->
<!-- wp:paragraph --><p>独立在线演示和公开代码仓库仍在整理中，后续只有在完成密钥、日志、测试数据和隐私配置检查后才会补充正式链接；在此之前不提供无法复核或可能暴露私人资料的占位地址。</p><!-- /wp:paragraph -->
BLOCKS;
}

function seed_site(): array {
	$sources = array(
		'profile'  => read_approved_source( '个人介绍/个人介绍.md', 'kb-pub-001' ),
		'career'   => read_approved_source( '个人介绍/教育与实习经历.md', 'kb-pub-002' ),
		'skills'   => read_approved_source( '个人介绍/技能清单.md', 'kb-pub-005' ),
		'intent'   => read_approved_source( '个人介绍/兴趣爱好与求职意向.md', 'kb-pub-006' ),
		'contact'  => read_approved_source( '个人介绍/联系方式.md', 'kb-pub-007' ),
		'resume'   => read_approved_source( '个人介绍/公开简历.md', 'kb-pub-009' ),
		'worldcup' => read_approved_source( '项目展示/世界杯百科智能问答BOT.md', 'kb-pub-003' ),
		'jobrag'   => read_approved_source( '项目展示/AI求职知识库RAG.md', 'kb-pub-004' ),
	);

	update_option( 'blogname', '钟伟达' );
	update_option( 'blogdescription', 'AI 应用交付 / FDE 个人简历与项目作品集' );
	update_option( 'blog_public', '0' );
	update_option( 'timezone_string', 'Asia/Shanghai' );
	update_option( 'date_format', 'Y-m-d' );
	update_option( 'permalink_structure', '/%postname%/' );
	update_option( 'default_comment_status', 'closed' );
	update_option( 'default_ping_status', 'closed' );
	cleanup_starter_content();

	$worldcup_id = upsert_post(
		array(
			'post_type'      => 'project',
			'post_status'    => 'publish',
			'post_title'     => '世界杯百科智能问答 BOT',
			'post_name'      => 'world-cup-rag-bot',
			'post_excerpt'   => '基于 Dify 与 RAG 搭建的世界杯主题知识库问答应用，将分散的赛事资料整理为可检索内容，并围绕文档预处理、知识库切片、检索配置、Prompt 优化、多场景问答和嵌入方式完成实践。',
			'post_content'   => project_content_world_cup(),
			'menu_order'     => 1,
			'comment_status' => 'closed',
		),
		array(
			'_zwd_source_id'            => $sources['worldcup']['id'],
			'_zwd_source_path'          => $sources['worldcup']['path'],
			'_zwd_source_updated_at'    => $sources['worldcup']['updated_at'],
			'_zwd_project_role_summary' => '资料预处理、知识库配置、Prompt 优化与问答调试',
		)
	);
	wp_set_object_terms( $worldcup_id, array( 'Dify', 'RAG', 'Prompt Engineering' ), 'project_skill', false );

	$jobrag_id = upsert_post(
		array(
			'post_type'      => 'project',
			'post_status'    => 'publish',
			'post_title'     => '个人求职知识库问答系统',
			'post_name'      => 'ai-job-rag-assistant',
			'post_excerpt'   => '面向个人求职资料构建的代码型 RAG 知识库问答系统，将教育经历、项目证据、岗位资料与复盘记录统一组织，并通过分层索引、增量更新、来源引用和隐私隔离，让公开问答保持可追溯、可维护且不越过个人资料边界。',
			'post_content'   => project_content_job_rag(),
			'menu_order'     => 2,
			'comment_status' => 'closed',
		),
		array(
			'_zwd_source_id'            => $sources['jobrag']['id'],
			'_zwd_source_path'          => $sources['jobrag']['path'],
			'_zwd_source_updated_at'    => $sources['jobrag']['updated_at'],
			'_zwd_project_role_summary' => '知识库结构、隐私分层、检索问答与本地验收',
		)
	);
	wp_set_object_terms( $jobrag_id, array( 'FastAPI', 'LangChain', 'Qdrant', 'RAG' ), 'project_skill', false );

	$obsolete_insights_page = get_page_by_path( 'insights', OBJECT, 'page' );
	if ( $obsolete_insights_page instanceof \WP_Post ) {
		wp_delete_post( $obsolete_insights_page->ID, true );
	}

	$pages = array(
		array( 'title' => '首页', 'slug' => 'home', 'order' => 0, 'content' => home_content() ),
		array( 'title' => '隐私说明', 'slug' => 'privacy', 'order' => 99, 'content' => privacy_content() ),
	);

	$page_ids = array();
	foreach ( $pages as $page ) {
		$page_ids[ $page['slug'] ] = upsert_post(
			array(
				'post_type'      => 'page',
				'post_status'    => 'publish',
				'post_title'     => $page['title'],
				'post_name'      => $page['slug'],
				'post_content'   => $page['content'],
				'menu_order'     => $page['order'],
				'comment_status' => 'closed',
			)
		);
	}

	update_option( 'show_on_front', 'page' );
	update_option( 'page_on_front', $page_ids['home'] );
	update_option( 'wp_page_for_privacy_policy', $page_ids['privacy'] );
	migrate_single_page( false );
	flush_rewrite_rules();

	return array(
		'pages'   => $page_ids,
		'projects' => array( $worldcup_id, $jobrag_id ),
		'form'     => 0,
	);
}

function migrate_single_page( bool $flush = true ): array {
	$deleted_pages = 0;
	foreach ( array( 'about', 'resume', 'contact' ) as $slug ) {
		$page = get_page_by_path( $slug, OBJECT, 'page' );
		if ( $page instanceof \WP_Post ) {
			wp_delete_post( $page->ID, true );
			++$deleted_pages;
		}
	}

	$deleted_forms = 0;
	if ( post_type_exists( 'wpcf7_contact_form' ) ) {
		$form = get_page_by_path( 'recruitment-contact', OBJECT, 'wpcf7_contact_form' );
		if ( $form instanceof \WP_Post ) {
			wp_delete_post( $form->ID, true );
			++$deleted_forms;
		}
	}

	update_option( 'zwd_single_page_migrated', VERSION );
	if ( $flush ) {
		flush_rewrite_rules();
	}

	return array(
		'pages' => $deleted_pages,
		'forms' => $deleted_forms,
	);
}

function verify_site(): array {
	$errors = array();
	$pages  = array( 'home', 'privacy' );

	foreach ( $pages as $slug ) {
		$page = get_page_by_path( $slug, OBJECT, 'page' );
		if ( ! $page instanceof \WP_Post || 'publish' !== $page->post_status ) {
			$errors[] = '缺少已发布页面：' . $slug;
		}
	}

	$published_pages = get_posts(
		array(
			'post_type'      => 'page',
			'post_status'    => 'publish',
			'posts_per_page' => -1,
		)
	);
	if ( 2 !== count( $published_pages ) ) {
		$errors[] = '当前公开页面数量应为 2，当前为 ' . count( $published_pages );
	}

	foreach ( array( 'about', 'resume', 'contact' ) as $retired_slug ) {
		if ( get_page_by_path( $retired_slug, OBJECT, 'page' ) instanceof \WP_Post ) {
			$errors[] = '已下线页面仍然存在：' . $retired_slug;
		}
	}

	$removed_insights_page = get_page_by_path( 'insights', OBJECT, 'page' );
	if ( $removed_insights_page instanceof \WP_Post ) {
		$errors[] = '文章页面 insights 应已删除。';
	}

	$published_articles = get_posts(
		array(
			'post_type'      => 'post',
			'post_status'    => 'publish',
			'posts_per_page' => -1,
		)
	);
	if ( ! empty( $published_articles ) ) {
		$errors[] = '首版不应包含未经审核的已发布文章。';
	}

	$projects = get_posts(
		array(
			'post_type'      => 'project',
			'post_status'    => 'publish',
			'posts_per_page' => -1,
		)
	);
	if ( count( $projects ) < 2 ) {
		$errors[] = '已发布项目数量至少应为 2，当前为 ' . count( $projects );
	}

	if ( '0' !== (string) get_option( 'blog_public' ) ) {
		$errors[] = '本地站必须保持 noindex。';
	}

	$public_posts = get_posts(
		array(
			'post_type'      => array( 'page', 'project' ),
			'post_status'    => 'publish',
			'posts_per_page' => -1,
		)
	);
	$forbidden_patterns = array(
		'/\bsk-[a-z0-9_-]{12,}\b/i' => '疑似 API 密钥',
		'/bearer\s+[a-z0-9._-]+/i'  => '疑似 Bearer Token',
	);
	foreach ( $public_posts as $post ) {
		$text = wp_strip_all_tags( $post->post_title . ' ' . $post->post_excerpt . ' ' . $post->post_content );
		if ( 'home' !== $post->post_name && preg_match( '/\b1[3-9]\d{9}\b/u', $text ) ) {
			$errors[] = sprintf( '疑似手机号出现在：%s', $post->post_title );
		}
		foreach ( $forbidden_patterns as $pattern => $label ) {
			if ( preg_match( $pattern, $text ) ) {
				$errors[] = sprintf( '%s 出现在：%s', $label, $post->post_title );
			}
		}
	}

	foreach ( $projects as $project ) {
		foreach ( array( '_zwd_source_id', '_zwd_source_path', '_zwd_source_updated_at', '_zwd_project_role_summary' ) as $meta_key ) {
			if ( '' === (string) get_post_meta( $project->ID, $meta_key, true ) ) {
				$errors[] = sprintf( '项目“%s”缺少来源字段 %s', $project->post_title, $meta_key );
			}
		}
	}

	return $errors;
}

if ( defined( 'WP_CLI' ) && WP_CLI ) {
	class CLI_Command {
		public function seed(): void {
			$result = seed_site();
			\WP_CLI::success( sprintf( '已生成 %d 个页面和 %d 个项目。', count( $result['pages'] ), count( $result['projects'] ) ) );
		}

		public function verify(): void {
			$errors = verify_site();
			if ( ! empty( $errors ) ) {
				foreach ( $errors as $error ) {
					\WP_CLI::warning( $error );
				}
				\WP_CLI::error( '网站验收未通过。' );
			}

			\WP_CLI::success( '网站结构、公开项目和基础隐私检查通过。' );
		}

		public function migrate_single_page(): void {
			$result = migrate_single_page();
			\WP_CLI::success(
				sprintf(
					'单页迁移完成：删除 %d 个旧页面、%d 个旧联系表单。',
					$result['pages'],
					$result['forms']
				)
			);
		}
	}

	\WP_CLI::add_command( 'zwd', __NAMESPACE__ . '\\CLI_Command' );
	\WP_CLI::add_command(
		'zwd migrate-single-page',
		static function (): void {
			$result = migrate_single_page();
			\WP_CLI::success(
				sprintf(
					'单页迁移完成：删除 %d 个旧页面、%d 个旧联系表单。',
					$result['pages'],
					$result['forms']
				)
			);
		}
	);
}
